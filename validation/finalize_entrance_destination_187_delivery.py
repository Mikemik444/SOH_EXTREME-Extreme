"""Bind executed 1.8.7 evidence to the complete replacement-source delivery."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.7-source-files"
TESTS = ROOT / "tests"
REPORTS = (
    "entrance_187_destination_audit.json",
    "entrance_187_destination_policy_validation.json",
    "entrance_destination_187_validation.json",
    "entrance_destination_187_full_graph_probe.json",
    "entrance_destination_187_core_regressions.json",
    "entrance_187_native_integration_review.json",
    "entrance_destination_187_native_safety_validation.json",
    "entrance_destination_187_native_bridge_validation.json",
    "entrance_destination_187_spawn_lifecycle_validation.json",
    "entrance_destination_187_full_fill_child.json",
    "entrance_destination_187_full_fill_adult.json",
    "entrance_destination_187_apworld_validation.json",
    "entrance_destination_187_version_validation.json",
    "entrance_destination_187_source_build_validation.json",
    "entrance_destination_187_source_completeness.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = PACKAGE / "SOURCE_FILES.json"
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["version"] == "1.8.7"
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    for name, digest in expected.items():
        assert sha(SOURCE / name) == digest == sha(PACKAGE / name), name
    validation = PACKAGE / "validation"
    validation.mkdir(exist_ok=True)
    loaded, report_hashes, verified, auxiliary_verified = {}, {}, 0, 0
    accepted = {"passed", "passed_source_destination_audit", "passed_independent_source_review", True}
    for name in REPORTS:
        path = TESTS / name
        data = json.loads(path.read_bytes())
        status = data.get("status", data.get("passed"))
        assert status in accepted, (name, status)
        for field in ("source_sha256", "source_hashes", "sources", "test_sha256"):
            for relative, digest in data.get(field, {}).items():
                assert isinstance(digest, str) and len(digest) == 64, (name, field, relative)
                assert sha(SOURCE / relative) == digest, (name, relative, "stale executed/reviewed source")
                verified += 1
        for field in ("dependency_sha256", "header_hashes", "native_header_hashes"):
            for relative, digest in data.get(field, {}).items():
                assert sha(TESTS / "entrance_184_native_dependencies" / relative) == digest, (name, relative)
                auxiliary_verified += 1
        for relative, digest in data.get("fixture_sha256", {}).items():
            assert sha(ROOT / relative) == digest, (name, relative)
            auxiliary_verified += 1
        loaded[name] = data
        report_hashes[name] = {"status": status, "sha256": sha(path)}
        shutil.copyfile(path, validation / name)

    completeness = loaded["entrance_destination_187_source_completeness.json"]
    assert completeness["source_sha256"] == expected
    assert completeness["all_previous_replacement_files_retained"]
    apworld_sha = sha(PACKAGE / "soh_extreme.apworld")
    assert apworld_sha == sha(SOURCE / "archipelago/soh_extreme.apworld")
    for name in ("entrance_destination_187_apworld_validation.json", "entrance_destination_187_version_validation.json"):
        assert loaded[name]["archive_sha256"] == apworld_sha
    build = loaded["entrance_destination_187_source_build_validation.json"]
    assert build["manifest_sha256"] == sha(manifest_path)
    assert build["apworld_sha256"] == apworld_sha
    for name, digest in build["helper_sha256"].items():
        assert sha(PACKAGE / name) == digest
    yaml_sha = sha(PACKAGE / "SOH-EXTREME.yaml")
    assert yaml_sha == "30af887663cd55d0408176a9b5f23b3ee25eb0ff9098ea10ace0c749811128f5"

    # Include exact small inputs and runnable evidence; do not alter test sources
    # to conceal their original workspace paths or execution dependencies.
    proof_files = (
        "run_destination_safety_187.py", "probe_entrance_age_187.py",
        "run_entrance_core_regressions_187.py", "entrance_destination_187_run_full_fill.py",
        "finder_hints_186_validate_apworld.py", "entrance_destination_187_source_build_check.py",
        "entrance_184_source_build_probe.ps1", "entrance_184_native_dependencies_provenance.json",
        "entrance_184_bridge_child_cvars.json", "entrance_184_bridge_adult_cvars.json",
        "finalize_entrance_destination_187_delivery.py",
    )
    for name in proof_files:
        shutil.copyfile(TESTS / name, validation / name)
    dependencies = validation / "native_dependencies"
    dependencies.mkdir(exist_ok=True)
    for path in (TESTS / "entrance_184_native_dependencies").iterdir():
        if path.is_file():
            shutil.copyfile(path, dependencies / path.name)

    count = len(expected)
    delta_count = len(completeness["changed_since_1.8.6"])
    fills = {}
    for age in ("child", "adult"):
        data = loaded[f"entrance_destination_187_full_fill_{age}.json"]
        player = data["validation"]["players"]["1"]
        assert data["world_version"] == "1.8.7" and data["yaml_sha256"] == yaml_sha
        assert data["source_unchanged_during_run"] and player["goal_met"]
        assert player["checked"] == player["network_checks"] == 4036
        assert data["initial_hyrule_field_reachable"] and data["saved_mixed_entrance_pools"] == ["all"]
        hint = data["hint_generation"][-1]
        assert hint["destination_policy_revision"] == 1 and hint["reviewed_mapped_arrivals"] == 719
        fills[age] = {
            "network_checks": player["network_checks"], "goal_met": True,
            "initial_network_checks": data["initial_network_checks"],
            "initial_physical_checks": data["initial_physical_checks"],
            "initial_hyrule_field_reachable": True,
            "child_spawn": data["child_spawn"], "adult_spawn": data["adult_spawn"],
            "overworld_endpoints": data["overworld_endpoints"],
            "changed_overworld_endpoints": data["changed_overworld_endpoints"],
            "hint_kinds": hint["hint_rows_by_kind"],
        }
    ap_cases = loaded["entrance_destination_187_validation.json"]["test_cases"]
    policy_cases = loaded["entrance_187_destination_policy_validation.json"]["case_count"]
    assert ap_cases == 35 and policy_cases == 17
    native = loaded["entrance_destination_187_native_safety_validation.json"]["cases"]
    assert native["catalog"]["reviewed_endpoints"] == 719
    assert native["catalog"]["verified_normal_table_entries"] == 2876
    summary = {
        "status": "passed", "version": "1.8.7", "utc": datetime.now(timezone.utc).isoformat(),
        "layout": "complete_source_files", "complete_replacement_source_files": count,
        "changed_or_added_since_1.8.6": delta_count, "source_sha256": expected,
        "verified_report_source_hash_entries": verified, "verified_fixture_hash_entries": auxiliary_verified,
        "current_reports": report_hashes, "apworld_sha256": apworld_sha, "yaml_sha256": yaml_sha,
        "manifest_sha256": sha(manifest_path), "build_helpers_sha256": build["helper_sha256"],
        "catalog": loaded["entrance_187_destination_audit.json"]["coverage"],
        "native_boundary_cases": native, "full_fills": fills,
        "limitations": [
            "The uploaded source lacks the root CMake project, native build dependencies, and ROM scene collision assets.",
            "No complete Windows game build, live AP server session, ImGui run, or in-game playthrough was performed here.",
            "Native regressions compile actual production functions and scene-selection blocks with engine I/O isolated.",
            "Destination auditing proves the reviewed resolver/table facts, not ROM spawn geometry or every physical action sequence.",
            "Both full fills pass under the AP logic model for these two seeds; this does not prove every possible seed.",
            "Prior Finder, hint, soul, Lost Woods and other cumulative changes are retained; their separate 1.8.6 evidence is historical.",
        ],
    }
    (validation / "entrance_destination_187_release_validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    child, adult = fills["child"], fills["adult"]

    readme = f"""SOH-EXTREME 1.8.7 - Complete replacement source files
====================================================

This cumulative package includes {count} complete source replacements and the
matching soh_extreme.apworld. All previous 1.8.6 replacement files are retained.
Use this single ZIP to merge the update into your complete checkout.

WHAT CHANGED IN 1.8.7
--------------------
Entrance randomization now shares an explicit reviewed destination policy
between the AP generator and the native runtime. All 719 catalog endpoints
and their 2,876 ordinary child/adult, day/night scene-and-spawn resolutions are
covered. Cutscene-only scenes, debug entries, unused scenes and unreviewed
endpoints are excluded. A new endpoint or changed resolver fact requires an
explicit policy review; merely being inside the native table is insufficient.

The native transition fade and Play_Init now protect a randomized arrival
against inherited cutscene state. That state could previously turn a valid
destination into a debug/unused scene or an out-of-range table access. Ordinary
arrivals use their reviewed age/time setup. Legitimate newly scheduled story
cutscenes retain their events, flags and rewards.

AGE REQUIREMENTS AND STARTING ROUTES
-----------------------------------
Generation checks child and adult physical reachability separately, preserving
the existing item, movement, soul, combat and age predicates on source exits.
It checks age-restricted destinations even when the return exit belongs to an
unshuffled pool. Shared interiors do not gain an artificial age gate that could
hide an invalid arrival from the logic model.

The castle fairy exits and Hyrule Castle Storms Grotto return have explicit
arrival-age restrictions grounded in the native entrance randomizer's explicit
child/adult restrictions. This does not
apply a blanket age ban to dungeons: valid mixed-age routes still use their
actual traversal and item requirements.

Each enabled randomized age spawn now needs its OWN usable physical return
and initial-inventory route to Hyrule Field, including the non-starting age.
The starting age also needs a real eligible progression check beyond Link's
Pocket. Future pool items do not certify an initial escape. Water Temple's
initial Swim requirement remains in effect. Generation does not grant extra
starting items or change the configured age to make a route pass.

The native guard checks Link's actual age without converting child to adult
or adult to child. If an invalid arrival reaches the runtime, recovery tries
the source's reverse directly without shuffling it again, then the same age's
mapped spawn, then the verified dry Link's House entrance. Recovery does not
award a traversal check. If every recovery table is invalid, it refuses the
scene load. This is an exceptional recovery path, not the normal spawn rule.

Native AP-only routing now activates the existing child blue-warp repairs and
physical grotto resolution even when the corresponding local native toggles
are off. Coupled grotto returns preserve their recorded return room/position.

CUMULATIVE FEATURES RETAINED
---------------------------
Paired entrances and returns; the overworld entrance option; mixed pool all
meaning every enabled pool; child/adult randomized spawns and save-to-spawn;
Jabu room/door traversal fixes; descriptive check names in Finder and AP;
optional room/door numbers; omitted singleton region headers; automatic zone
dropdowns with persistent manual choices; complete A-to-continue hint paging;
progression-item hints sent to AP with WOTH/barren hints retained in game;
same-save tracker continuity; invisible solid soul-gated objects and
interactable path-blocking NPCs; and the Lost Woods scale/route corrections.
All entrance-randomizer settings remain marked Experimental.

INSTALL AND BUILD
-----------------
1. Close the game and finish any active build.
2. Extract this ZIP directly into your existing COMPLETE checkout:
     E:\\test\\bb\\
   Merge soh\\, src\\, archipelago\\ and tools\\, replacing included files.
   Retain the rest of your checkout, including the root CMakeLists.txt and
   configured build-vs directory. There is no payload subfolder to navigate.
   Example final paths for this update:
     E:\\test\\bb\\src\\code\\z_play.c
     E:\\test\\bb\\soh\\Network\\Archipelago\\EntranceDestinationPolicy.h
     E:\\test\\bb\\soh\\Network\\Archipelago\\EntranceDestinationData.inc
     E:\\test\\bb\\archipelago\\soh_extreme\\EntranceSafety.py
     E:\\test\\bb\\archipelago\\soh_extreme\\EntranceDestinationPolicy.json

3. From E:\\test\\bb, run:
     BUILD_RELEASE.cmd -RepositoryPath "E:\\test\\bb" -BuildDirectory "build-vs"
   The banner must say 1.8.7 and build helper revision 4. It verifies all
   {count} delivered files, then clean-builds the configured Release setup:
     cmake --build build-vs --config Release --parallel 8 --clean-first
   Wait for success and launch the exact Game executable path it prints.
   Build logs and build-receipt.json are written under soh-extreme-builds\\.

4. Install the top-level soh_extreme.apworld from this ZIP at:
     C:\\ProgramData\\Archipelago\\custom_worlds\\soh_extreme.apworld
   Update both generation and tracker installations if separate, then restart
   them. Both copies of the APWorld in this package are identical.

5. Generate a fresh seed with the updated APWorld and the supplied
   SOH-EXTREME.yaml. The YAML is your file unchanged, including age weights and
   starting items. Create the matching AP save and connect to its server/slot.
   Existing servers keep their old maps and item data. An unsafe saved map
   rejected by the new AP age-policy checks must be regenerated.

6. Confirm native version 1.8.7 in Network -> Archipelago, then check its
   entrance-map status and the displayed child/adult spawn destinations.

VALIDATION
----------
Both complete official AP 0.6.7 fills with your YAML reached all 4,036 network
checks and the goal. Initial child: {child['initial_network_checks']} network / {child['initial_physical_checks']} physical checks.
Initial adult: {adult['initial_network_checks']} network / {adult['initial_physical_checks']} physical checks. Both had initial Hyrule Field
access. The child-start run changed {child['changed_overworld_endpoints']}/52 overworld endpoints; the adult-start run
changed {adult['changed_overworld_endpoints']}/52. Final hints preserved placements and RNG state, with direct item,
Way of the Hero and barren rows retained. These are two seed-specific logic
validations, not a proof of every possible world.

Focused validation passed {policy_cases} policy-generator cases, {ap_cases} AP safety/age cases,
six complete-world age probes, and 40 retained start/pool/restore regressions.
Native ASan/UBSan boundary tests verified all 2,876 normal table entries,
2,870 age-allowed arrivals, 1,684 room-door arrivals, 60 stale-cutscene cases,
actual story handlers, and seven recovery cases. Both retained 719-route
native bridge fixtures and all eight spawn-lifecycle cases also passed.
The official ZIP loader verified 120 entries and version parity at 1.8.7.

The supplied source snapshot does not contain the root CMake project,
external native build dependencies, or extracted ROM collision assets. The
complete game was not built or played here. Native tests use production
functions with engine I/O isolated; rebuild your full checkout for live-game
verification. VALIDATION.txt and validation/ contain the exact evidence.
"""
    (PACKAGE / "README.txt").write_text(readme, encoding="utf-8")
    notes = f"""SOH-EXTREME 1.8.7 - Validation evidence and limits
=================================================

PASS for the scoped checks below. The aggregate report is
validation/entrance_destination_187_release_validation.json. It binds all
{count} complete source replacements to final SHA-256 values, checks {verified}
report/source/test hash entries and {auxiliary_verified} dependency/fixture hashes, and records
every current report hash. {delta_count} files changed or were added since 1.8.6.

CURRENT EVIDENCE
----------------
Destination policy: all 719 endpoints (232 direct native, 33 grotto loads,
33 grotto returns, 421 room doors), 2,876 ordinary age/time resolutions,
83 declared scenes and 90 resolved variants are covered. Native group bases,
door anchors/coordinates, exact virtual grotto ranges, alias repairs, and all
719 compiled endpoint rows match. No declared cutscene/debug/unknown scene
is approved. Debug-only duplicate entry 0x2EA is excluded even though it
reuses a playable scene. All 17 generator mutation/regeneration cases pass.
This establishes source-level table/resolver facts, not ROM collision data.

AP age safety: 35 cases run against real AP CollectionState/SohRegion and the
production safety/entrance helpers. They exercise per-age physical reachability,
restricted identity exits in disabled pools, malformed policy/catalog data,
one-way sources, and both spawn ages' initial-inventory escape requirements.
Six full source-world probes execute actual rules for castle fairy/grotto
restrictions and fresh candidate state. Forty retained AP regressions cover
initial checks, movement/items, paired overworld/mixed pools, all expansion,
and saved-map restoration.

Native boundary suite: actual table construction, entrance/grotto/warp
resolution, ConditionalTriggers, transition-fade selection and Play_Init's
scene-selection block compile with ASan and UBSan. All 2,876 table entries,
2,870 age-allowed arrivals, 1,684 room-door arrivals and 56 scene-variant check
identities pass. Sixty inherited-cutscene cases cover unused/debug/OOB table
failures. Eight invalid-map cases reject atomically. Seven recovery cases
verify direct reverse, actual-age spawn, verified house, and refusal when no
table remains valid. Six warp songs, five child bluewarp repairs, and AP-only
physical grotto entry/return execute their production paths.

The production Requiem, Saria item/flag, Light Arrow and Nocturne conditional
handlers retain their intended behavior. Unarmed ordinary story paths remain
unchanged. A separate nine-part source integration review found no material
defect in marker lifetime, call boundaries, recovery, or story preservation.

Native retained bridge: both legacy 1.8.4 CVar maps were rerun against 1.8.7
source with ASan/UBSan. Each covers 719 routes, 692 coupled returns, all 421
physical door directions (75 Jabu cases), 232 native scene and 14 dynamic
lookups, canceled/dead crossing rejection, and both-age cached/late/save loads.
The eight-case spawn lifecycle suite is warning-clean with C++20 and
-Wall -Wextra -Werror. Legacy maps are retained regression inputs; they do not
claim to be fresh seeds generated by the current age-policy validator.

Native engine, render, network and session I/O are isolated where required by
the fragment harnesses. Leak scanning is disabled because process inspection
is restricted here. No complete Windows binary or gameplay pass is claimed.

Full generation: official AP 0.6.7 Main.main through pre_output, restrictive
fill and all-check/goal validation, seed 1, once per forced starting age.
Both runs reach all 4,036 checks and the goal under the AP model. Child has
{child['initial_network_checks']} initial network / {child['initial_physical_checks']} physical checks; adult has {adult['initial_network_checks']} / {adult['initial_physical_checks']}. Both can initially
reach Hyrule Field. The child/adult runs change {child['changed_overworld_endpoints']}/52 and {adult['changed_overworld_endpoints']}/52 overworld endpoints.
All 719 exported arrivals carry policy revision 1. Only configured starting
items are precollected; the supplied YAML is unchanged. Repeated final hints
are deterministic and preserve placement and per-slot RNG state while the
official output global-RNG guard remains active. These two seeds cannot prove
every generated seed or every physical player action.

APWorld: official ZIP import with the loose world temporarily absent verifies
120 archive entries / 119 package files, resource parity, all JSON, and six
native/tracker/archive version values at 1.8.7. The loose world is restored.

Build helper: the shipped revision-4 PowerShell AST preflight verifies all
{count} copied files in a disposable fixture. Helpers differ from 1.8.6 only in
release strings. This runs on Linux PowerShell 7.6.7 with OS-check bypass and
equivalent Unix path handling, not Windows/MSBuild or a complete game build.

Cumulative package: byte comparison covers all {completeness['original_source_files']} original files and the
current source. No original file is missing and all previous replacements are
retained. No source change lies outside the manifest. Both APWorld copies and
the original user YAML match exactly. Final ZIP creation verifies inventory,
all source bytes and CRC. Its final hash is recorded outside the ZIP to avoid
a self-referential checksum.

HISTORICAL EVIDENCE
------------------
validation/previous_1.8.6/ contains the previous aggregate and VALIDATION.txt.
Those describe earlier Finder, hints, souls, Lost Woods, Experimental labels,
Jabu and entrance work. They are historical evidence, not claims that every
separate 1.8.6 suite was rerun for this release.

REPRODUCTION
------------
Production regressions are included under tools/tests/. The AP age suite and
native boundary runner have distinct filenames. Additional release wrappers,
the retained bridge inputs and native table/header fixtures are in validation/.
Their SHA-256 provenance is included. Generator verification accepts either a
complete checkout's include directory or validation/native_dependencies/.
The fixtures contain no extracted ROM scene assets.

Use official AP 0.6.7 source/dependencies for Python world tests and a supported
C++ compiler for native fragments. Some release scripts retain the original
workspace paths and sibling test layout; adjust them for your local checkout.
README.txt provides Windows merge/build instructions and APWorld installation.
"""
    (PACKAGE / "VALIDATION.txt").write_text(notes, encoding="utf-8")
    print(json.dumps({"status": "passed", "source_files": count, "changed_since_1.8.6": delta_count,
                      "reports": len(REPORTS), "verified_source_hashes": verified,
                      "verified_fixture_hashes": auxiliary_verified, "full_fills": fills}))


if __name__ == "__main__":
    main()
