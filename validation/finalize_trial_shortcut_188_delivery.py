"""Bind executed 1.8.8 evidence to the cumulative replacement source files."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
TESTS = ROOT / "tests"
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.8-source-files"
REPORTS = (
    "trial_medallion_188_ap_validation.json",
    "medallion_trial_native_validation.json",
    "entrance_blockers_188_ap_validation.json",
    "scene_flag_lifecycle_validation.json",
    "temporary_shutter_188_independent_review.json",
    "jabu_tentacle_arrival_native_review.json",
    "trial_shortcut_188_core_regressions.json",
    "jabu_carry_188_validation.json",
    "trial_shortcut_188_full_fill_child.json",
    "trial_shortcut_188_full_fill_adult.json",
    "trial_shortcut_188_apworld_validation.json",
    "trial_shortcut_188_version_validation.json",
    "trial_shortcut_188_source_build_validation.json",
    "trial_shortcut_188_source_completeness.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = PACKAGE / "SOURCE_FILES.json"
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["version"] == "1.8.8"
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    for name, digest in expected.items():
        assert sha(SOURCE / name) == digest == sha(PACKAGE / name), name
    validation = PACKAGE / "validation"
    validation.mkdir(exist_ok=True)
    loaded, report_hashes = {}, {}
    verified, auxiliary_verified = 0, 0
    for name in REPORTS:
        path = TESTS / name
        data = json.loads(path.read_bytes())
        status = data.get("status", data.get("passed"))
        if name == "temporary_shutter_188_independent_review.json":
            assert data["review_kind"] == "independent read-only source review"
            assert data["production_edits"] is False and data["test_execution"] is False
            assert data["concrete_new_defect_found"] is False
            status = "completed_source_review"
        elif name == "jabu_tentacle_arrival_native_review.json":
            assert status == "reviewed"
        else:
            assert status is True or isinstance(status, str) and status.startswith("passed"), (name, status)
        for field in ("source_sha256", "source_hashes", "sources", "test_sha256"):
            for relative, digest in data.get(field, {}).items():
                assert isinstance(digest, str) and len(digest) == 64, (name, field, relative)
                assert sha(SOURCE / relative) == digest, (name, relative, "stale source or test")
                verified += 1
        for field in ("dependency_sha256", "header_hashes", "native_header_hashes"):
            for relative, digest in data.get(field, {}).items():
                assert sha(TESTS / "entrance_184_native_dependencies" / relative) == digest, (name, relative)
                auxiliary_verified += 1
        for relative, digest in data.get("fixture_sha256", {}).items():
            assert sha(ROOT / relative) == digest, (name, relative)
            auxiliary_verified += 1
        if data.get("reference_runtime_hashes"):
            assert data["reference_runtime_version"] == "0.6.8"
            for relative, digest in data["reference_runtime_hashes"].items():
                assert sha(ROOT / "ap-runtime-068" / relative) == digest, (name, relative)
                auxiliary_verified += 1
        loaded[name] = data
        report_hashes[name] = {"status": status, "sha256": sha(path)}
        shutil.copyfile(path, validation / name)

    completeness = loaded["trial_shortcut_188_source_completeness.json"]
    assert completeness["source_sha256"] == expected
    assert completeness["all_previous_replacement_files_retained"]
    apworld_sha = sha(PACKAGE / "soh_extreme.apworld")
    assert apworld_sha == sha(SOURCE / "archipelago/soh_extreme.apworld")
    for name in ("trial_shortcut_188_apworld_validation.json", "trial_shortcut_188_version_validation.json"):
        assert loaded[name]["archive_sha256"] == apworld_sha
    build = loaded["trial_shortcut_188_source_build_validation.json"]
    assert build["manifest_sha256"] == sha(manifest_path)
    assert build["apworld_sha256"] == apworld_sha
    for name, digest in build["helper_sha256"].items():
        assert sha(PACKAGE / name) == digest
    yaml_sha = sha(PACKAGE / "SOH-EXTREME.yaml")
    assert yaml_sha == "30af887663cd55d0408176a9b5f23b3ee25eb0ff9098ea10ace0c749811128f5"

    # The old seed is diagnostic evidence, not a passing test of new logic.
    reproduced_path = TESTS / "reported_seed_187_reproduction.json"
    reproduced = json.loads(reproduced_path.read_bytes())
    assert reproduced["status"] == "reproduced"
    assert reproduced["archipelago_version"] == "0.6.8" and reproduced["world_version"] == "1.8.7"
    assert reproduced["matching_placements"] == reproduced["network_checks"] == 4036
    assert reproduced["mismatched_placements"] == 0
    assert reproduced["yaml_sha256"] == yaml_sha
    spoiler_path = ROOT / "upload/AP_59333055637975796678_Spoiler.txt"
    assert reproduced["spoiler_sha256"] == sha(spoiler_path)
    shutil.copyfile(reproduced_path, validation / reproduced_path.name)
    runtime_path = TESTS / "archipelago_068_runtime_provenance.json"
    runtime = json.loads(runtime_path.read_bytes())
    assert runtime["version"] == "0.6.8" and runtime["missing_prior_files"] == []
    for relative, digest in runtime["source_hashes"].items():
        assert sha(ROOT / "ap-runtime-068" / relative) == digest, relative
        auxiliary_verified += 1
    shutil.copyfile(runtime_path, validation / runtime_path.name)
    for name in (
        "run_entrance_core_regressions_188.py", "trial_shortcut_188_run_full_fill.py",
        "finder_hints_186_validate_apworld.py", "trial_shortcut_188_source_build_check.py",
        "entrance_184_source_build_probe.ps1", "reproduce_reported_187_seed.py",
        "finalize_trial_shortcut_188_delivery.py",
    ):
        shutil.copyfile(TESTS / name, validation / name)
    shutil.copyfile(ROOT / "prepare_trial_shortcut_188_delivery.py", validation / "prepare_trial_shortcut_188_delivery.py")

    fills = {}
    for age in ("child", "adult"):
        data = loaded[f"trial_shortcut_188_full_fill_{age}.json"]
        player = data["validation"]["players"]["1"]
        assert data["archipelago_version"] == "0.6.8" and data["world_version"] == "1.8.8"
        assert data["yaml_sha256"] == yaml_sha and data["source_unchanged_during_run"]
        assert player["goal_met"] and player["checked"] == player["network_checks"] == 4036
        assert data["initial_hyrule_field_reachable"] and data["saved_mixed_entrance_pools"] == ["all"]
        hint = data["hint_generation"][-1]
        assert hint["destination_policy_revision"] == 1 and hint["reviewed_mapped_arrivals"] == 719
        fills[age] = {
            "seed": data["seed"], "network_checks": player["network_checks"], "goal_met": True,
            "initial_network_checks": data["initial_network_checks"],
            "initial_physical_checks": data["initial_physical_checks"],
            "initial_hyrule_field_reachable": True,
            "child_spawn": data["child_spawn"], "adult_spawn": data["adult_spawn"],
            "changed_overworld_endpoints": data["changed_overworld_endpoints"],
            "hint_kinds": hint["hint_rows_by_kind"],
        }
    assert loaded["trial_medallion_188_ap_validation.json"]["test_cases"] == 13
    assert loaded["trial_shortcut_188_core_regressions.json"]["test_cases"] == 40
    count = len(expected)
    delta_count = len(completeness["changed_since_1.8.7"])
    summary = {
        "status": "passed", "version": "1.8.8", "utc": datetime.now(timezone.utc).isoformat(),
        "layout": "complete_source_files", "complete_replacement_source_files": count,
        "changed_or_added_since_1.8.7": delta_count,
        "source_sha256": expected, "apworld_sha256": apworld_sha, "yaml_sha256": yaml_sha,
        "manifest_sha256": sha(manifest_path), "build_helpers_sha256": build["helper_sha256"],
        "verified_report_source_hash_entries": verified,
        "verified_fixture_and_runtime_hash_entries": auxiliary_verified,
        "current_reports": report_hashes,
        "reported_seed_reproduction": {
            "generation_seed": reproduced["seed"], "original_world_version": "1.8.7",
            "runtime": "Archipelago 0.6.8", "matching_placements": 4036,
            "mismatched_placements": 0, "report_sha256": sha(reproduced_path),
            "spoiler_sha256": reproduced["spoiler_sha256"],
        },
        "full_fills": fills,
        "native_medallion_cases": loaded["medallion_trial_native_validation.json"]["cases"],
        "native_scene_flag_cases": loaded["scene_flag_lifecycle_validation.json"]["cases"],
        "limitations": [
            "The uploaded snapshot lacks the root CMake project, full native build dependencies, and extracted ROM collision assets.",
            "No complete Windows game build, live AP session, ImGui run, or in-game playthrough was performed.",
            "Native fixtures execute extracted production functions with engine I/O isolated.",
            "Jabu damage-escape removal is a conservative logic correction supported by the reproduced dependency and user-observed blockage; it is not a collision simulation.",
            "Temporary-switch inventory and source review do not prove every room's switch approach geometry.",
            "Two full fills validate these seeds under the corrected AP logic model, not every possible seed.",
            "Old servers and generated placements retain their existing data; regenerate with the updated APWorld.",
            "Prior cumulative features are retained; separate 1.8.7 validation is historical unless rerun here.",
        ],
    }
    (validation / "trial_shortcut_188_release_validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    child, adult = fills["child"], fills["adult"]
    readme = fr"""SOH-EXTREME 1.8.8 - Complete replacement source files
====================================================

This cumulative ZIP contains {count} complete replacement source files and the
matching soh_extreme.apworld. All prior 1.8.7 replacement files are retained.
Merge it into your existing full checkout. The directories are at the ZIP
root: soh\, src\, archipelago\ and tools\.

JABU'S LIVE TENTACLE BARRIERS
---------------------------
The uploaded spoiler was reproduced using official Archipelago 0.6.8 and the
previous 1.8.7 APWorld: all 4,036 network item placements matched. Its internal
generation seed is 75502037396837836795; the filename contains another number.

In that map, the Temple of Time courtyard gossip-stone exit sends Link to the
northwest Jabu doorway beside the live tentacle. The old graph treated
TakeDamage as proof that Link could escape into the central corridor, exposing
the route to Open Chest on the lower-ledge/water-switch door. Surviving damage
does not prove that this arrival can pass the physical barrier.

All three vanilla To Fork -> Forked Corridor routes now require the matching
permanent tentacle-clear event. North West and North East require West;
North requires East. The generic damage escape is removed in both native
room logic and the AP graph. Legitimate direct arrivals into other rooms keep
their own local requirements. This does not apply a blanket adult Jabu ban.

Defeating a tentacle still requires its Soul and an age-usable Boomerang.
Merely owning a child-only item does not make adult combat possible.
The north room's return also now requires clearing all four Biri, whose
Soul is separate from the tentacle Soul. Killing the tentacle still records
its own permanent switch immediately; it does not falsely clear the room.

TRIAL MEDALLIONS
---------------
The physical source doorway keeps its requirements after shuffling, including
when scene-transition checks are disabled. Forest, Fire, Light and Spirit
trial returns require their own medallions when Medallion Locked Trials is on.
The reported Spirit Beamos Room -> Main check therefore requires the Spirit
Medallion even when its destination is Water Temple's Boss Key Room.

Water and Shadow returns preserve the actual native alternatives. Water
permits its Water Medallion or clearing the two Freezards. Shadow permits
its Shadow Medallion or clearing the Green Bubble and Like Like with access
to their actual platforms. Required Souls, usable combat and age rules still
apply to those clear actions. Forward medallion gates are retained.

Items already physically reachable through an alternate room arrival retain
their local collection requirements. A legacy whole-trial item overlay no
longer reattaches the original entrance medallion to exact ER collection routes.

SWITCHES AND SHORTCUTS
---------------------
Water Temple's 3 Jets No Switch -> Canal Alcove exit now needs access to the
actual switch side as the age using the door. Arriving at the far side no
longer treats the timed shutter as free. Walking over from the switch side,
or using a valid local return method to reach it, remains supported.

The age search now retries a blocked dependent exit when its required region
becomes reachable later in the search. A temporary switch is not converted
into a permanently collected AP event.

Native validation covers all 24 catalog temporary-switch shutters in both
directions, source/destination scene flags, ordinary room cleanup, respawn
flags, timers and existing recorded-switch replay. Permanent scene state
remains scoped to its physical scene. Existing authored recorded actions are
retained; arbitrary flags are not granted or copied into another dungeon.

The overworld pool includes Lost Woods <-> Goron City, Lost Woods <-> Zora's
River, and Lake Hylia <-> Zora's Domain. Internal Fire, Shadow and Spirit
shortcuts retain their physical switch/item/age logic. Crawlholes, open room
passages and movement within a room remain traversal paths; they are not
separate shuffled door endpoints. There is no dungeon/boss-shortcut setting
in the supplied fork or YAML.

CUMULATIVE FEATURES
-------------------
Paired entrances and returns; optional overworld entrances; mixed pool all
meaning every enabled pool; randomized child/adult spawns and save-to-spawn;
reviewed playable destinations and age restrictions; descriptive Finder/AP
names; optional room/door numbers; singleton header suppression; automatic
zone dropdowns with manual choices; A-to-continue hints; progression-item AP
hints and in-game Way of the Hero/barren hints; tracker continuity; solid
soul-gated objects and interactable path-blocking NPCs; Lost Woods access
corrections. All entrance-randomizer settings remain Experimental.

INSTALL AND BUILD
-----------------
1. Close the game and finish any active build.
2. Extract this ZIP directly into E:\test\bb\, merging its directories and
   replacing the included files. Keep the rest of your full checkout,
   including CMakeLists.txt and your configured build-vs directory.
3. From E:\test\bb, run:
     BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"
   The helper must report version 1.8.8 and revision 4. It verifies all
   {count} delivered source files, then performs the configured clean build:
     cmake --build build-vs --config Release --parallel 8 --clean-first
   Wait for success and launch the exact Game executable path it prints.
4. Install the top-level soh_extreme.apworld at:
     C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Update both generation and tracker installations if they are separate,
   then restart them. Both APWorld copies in this ZIP are identical.
5. Generate a fresh seed and create its matching AP save/server slot.
   The supplied SOH-EXTREME.yaml is your unchanged YAML. Correcting rules
   cannot relocate progression items in a previously generated server.
6. Confirm version 1.8.8 under Network -> Archipelago, then verify the
   entrance-map status and displayed child/adult spawn destinations.

VALIDATION
----------
The reported old seed was reproduced with 4,036/4,036 matching placements.
The new source passed 13 medallion AP test methods, 22 focused Jabu/switch/
shortcut tests, 40 retained start/pool/restore tests, and the retained
Jabu carried-Ruto suite. Native ASan/UBSan fixtures passed 1,152 directional
medallion cases plus 4 registration/unrelated-actor cases and 382 scene-flag
lifecycle cases. Reports distinguish executed tests from source-only review.

Both complete official AP 0.6.8 fills reached all 4,036 network checks and
the goal. The child-start run used seed {child['seed']}; the adult-start run
used the reported seed number {adult['seed']} with corrected source.
Initial child: {child['initial_network_checks']} network / {child['initial_physical_checks']} physical checks.
Initial adult: {adult['initial_network_checks']} network / {adult['initial_physical_checks']} physical checks.
Both had initial Hyrule Field access. Final hints preserved item placements
and RNG state and retained item, Way of the Hero and barren hints.

The full Windows game could not be built or played from the supplied partial
source snapshot. Native fixtures isolate engine I/O, and extracted ROM
collision assets were unavailable. These results are not a proof of every
seed or every physical path. Rebuild your full checkout for live validation.
See VALIDATION.txt and validation\ for the exact evidence and limits.
"""
    (PACKAGE / "README.txt").write_text(readme, encoding="utf-8")
    notes = f"""SOH-EXTREME 1.8.8 - Validation evidence and limits
=================================================

The aggregate report is validation/trial_shortcut_188_release_validation.json.
It binds all {count} replacement source files to final SHA-256 values,
verifies {verified} report/source/test entries and {auxiliary_verified}
fixture/runtime entries, and records each current evidence report's hash.
{delta_count} files changed or were added since the immutable 1.8.7 release.

EXECUTED CURRENT TESTS
---------------------
trial_medallion_188_ap_validation.json:
  13 AP test methods with all-six-trial, both-age and inventory subcases;
  source/check/rewiring parity, disabled settings, receipt/removal cache
  refresh, legitimate room clears and exact local collection routes.
entrance_blockers_188_ap_validation.json:
  Actual AP graph tests of tentacle-side arrivals, current age, enemy Souls,
  separate north-room Biri clear, timed Water switch approach, search order,
  and shortcut traversal/pool coverage: 22 test methods on AP 0.6.8.
jabu_carry_188_validation.json:
  Retained Ruto transport, local carrier doors and required actions.
trial_shortcut_188_core_regressions.json:
  40 retained tests of initial physical access, paired pools, all expansion,
  age/Swim/item restrictions and restoration of saved maps.
medallion_trial_native_validation.json:
  Actual medallion hook and directional shutter functions compiled with
  ASan/UBSan: 1,152 inventory/option/age/flag/direction cases plus 4
  registration/unrelated cases. The 48 clear alternatives and 72 switch-side
  rejections are subsets, not additional cases.
scene_flag_lifecycle_validation.json:
  382 native storage, save/restore, room cleanup, shutter, timer, respawn,
  recorded-action replay and scene-scoping cases. Player-init replay is
  distinguished from actor-context
  clearing, and other actor initialization may also reconstruct saved state.
trial_shortcut_188_full_fill_child.json / adult.json:
  Official AP 0.6.8 Main.main through complete restrictive fill and
  pre_output. Each reaches all 4,036 network checks and the goal, with a
  usable starting physical route and Hyrule Field access. Both final hint
  payloads are deterministic without changing placements or RNG.
trial_shortcut_188_apworld_validation.json / version_validation.json:
  Official ZIP-world loading, resource/byte parity and 1.8.8 version checks.
trial_shortcut_188_source_build_validation.json:
  Actual shipped revision-4 helper source preflight under PowerShell7 on
  Linux. This is source verification, not a Windows compile.

SOURCE REVIEW AND DIAGNOSTIC EVIDENCE
------------------------------------
temporary_shutter_188_independent_review.json:
  Read-only review of all 24 temporary shutter source predicates, explicit
  current-age region access, indirect dependencies and cache invalidation.
  Free native predicates were not given guessed item gates without layout
  evidence. Ruto/object state is distinguished from a bare temporary flag.
jabu_tentacle_arrival_native_review.json:
  Six Jabu branch endpoint/native records, room/side/offset/age parity and
  native/AP blocker conditions. Geometry and actual movement are unverified.
reported_seed_187_reproduction.json:
  The uploaded old seed recreated on official AP 0.6.8 with immutable 1.8.7:
  all 4,036 placements match. This diagnoses the old source; it is not a
  passing validation of that source's physical route.
archipelago_068_runtime_provenance.json:
  Official 0.6.8 archive URL, archive digest and extracted runtime hashes.

LIMITS
------
No full Windows game build, native UI run, live AP session or in-game
playthrough was performed. The uploaded source lacks the root CMake project,
complete dependencies and extracted ROM collision assets. Extracted native
functions run with engine I/O isolated. Jabu damage-escape removal is a
conservative correction to an unsupported route assumption backed by the
exact reproduced dependency and the user's blocked adult arrival.
The two full fills validate the corrected logic model for those seeds.
Existing generated placements and servers require a fresh generation.
Historical 1.8.7 validation remains under validation/previous_1.8.7 and is
not relabeled as current execution evidence.
"""
    (PACKAGE / "VALIDATION.txt").write_text(notes, encoding="utf-8")
    print(json.dumps({"status": "passed", "version": "1.8.8", "source_files": count,
                      "current_reports": len(REPORTS), "verified_source_entries": verified,
                      "verified_fixture_runtime_entries": auxiliary_verified,
                      "apworld_sha256": apworld_sha}))


if __name__ == "__main__":
    main()
