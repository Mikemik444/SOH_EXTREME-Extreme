"""Bind the cumulative 1.8.10 source release to current execution evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
TESTS = ROOT / 'tests'
PACKAGE = ROOT / 'delivery/SOH-EXTREME-1.8.10-source-files'
REPORTS = (
    'water_arrival_logic_1810.json',
    'water_logic_export_parity_1810.json',
    'water_1810_native.json',
    'gerudo_guard_card_native_validation.json',
    'richard_delivery_native_validation.json',
    'entrance_return_death_1810_native.json',
    'entrance_spawn_lifecycle_1810_native.json',
    'entrance_hallway_boundary_1810_native.json',
    'seed_safety_1810_regressions.json',
    'seed_safety_1810_entrance_blockers.json',
    'seed_safety_1810_full_fill_child.json',
    'seed_safety_1810_full_fill_adult.json',
    'seed_safety_1810_apworld_validation.json',
    'seed_safety_1810_version_validation.json',
    'seed_safety_1810_source_build_validation.json',
    'seed_safety_1810_source_completeness.json',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def main():
    manifest_path = PACKAGE / 'SOURCE_FILES.json'
    manifest = read(manifest_path)
    assert manifest['version'] == '1.8.10' and manifest['build_helper_revision'] == 4
    sources = {row['path']: row['sha256'] for row in manifest['files']}
    for name, digest in sources.items():
        assert sha(SOURCE / name) == digest == sha(PACKAGE / name), name
    validation = PACKAGE / 'validation'
    validation.mkdir(exist_ok=True)
    loaded, recorded = {}, {}
    source_bindings = other_bindings = 0
    for name in REPORTS:
        path = TESTS / name
        data = read(path)
        assert data['status'] == 'passed', (name, data.get('status'))
        for field in ('source_sha256', 'source_hashes', 'sources', 'test_sha256'):
            for relative, digest in data.get(field, {}).items():
                assert isinstance(digest, str) and len(digest) == 64, (name, field, relative)
                assert sha(SOURCE / relative) == digest, (name, relative, 'stale binding')
                source_bindings += 1
        for field in ('dependency_sha256', 'header_hashes', 'native_header_hashes'):
            for relative, digest in data.get(field, {}).items():
                assert sha(TESTS / 'entrance_184_native_dependencies' / relative) == digest, (name, relative)
                other_bindings += 1
        for field in ('fixture_sha256', 'input_sha256'):
            for relative, digest in data.get(field, {}).items():
                assert sha(ROOT / relative) == digest, (name, relative)
                other_bindings += 1
        if 'input_evidence_path' in data:
            assert sha(data['input_evidence_path']) == data['input_evidence_sha256']
            other_bindings += 1
        loaded[name] = data
        recorded[name] = {'status': data['status'], 'sha256': sha(path),
                          'scope': data.get('scope', data.get('limits'))}
        shutil.copyfile(path, validation / name)
    completeness = loaded['seed_safety_1810_source_completeness.json']
    assert completeness['source_sha256'] == sources
    assert completeness['all_previous_replacement_files_retained']
    apworld_sha = sha(PACKAGE / 'soh_extreme.apworld')
    for name in ('seed_safety_1810_apworld_validation.json', 'seed_safety_1810_version_validation.json'):
        assert loaded[name]['archive_sha256'] == apworld_sha
    build = loaded['seed_safety_1810_source_build_validation.json']
    assert build['manifest_sha256'] == sha(manifest_path)
    assert build['apworld_sha256'] == apworld_sha
    for name, digest in build['helper_sha256'].items():
        assert sha(PACKAGE / name) == digest
    original_yaml = ROOT / 'upload/SOH-EXTREME(20261017-230302).yaml'
    assert sha(original_yaml) == completeness['original_yaml_sha256'] == \
        '30af887663cd55d0408176a9b5f23b3ee25eb0ff9098ea10ace0c749811128f5'
    assert sha(PACKAGE / 'SOH-EXTREME.yaml') == completeness['yaml_sha256']

    fills = {}
    for age in ('child', 'adult'):
        data = loaded[f'seed_safety_1810_full_fill_{age}.json']
        player = data['validation']['players']['1']
        assert data['world_version'] == '1.8.10' and data['archipelago_version'] == '0.6.8'
        assert data['source_unchanged_during_run'] and data['age'] == age
        assert player['goal_met'] and player['checked'] == player['network_checks'] == 4036
        assert data['initial_hyrule_field_reachable'] and data['initial_physical_checks'] > 0
        assert data['saved_mixed_entrance_pools'] == ['all']
        assert data['yaml_sha256'] == sha(original_yaml)
        fills[age] = {key: data[key] for key in ('seed', 'age', 'child_spawn', 'adult_spawn',
                                                 'initial_network_checks', 'initial_physical_checks')}
        fills[age].update(goal_met=True, accessible_checks=4036, total_checks=4036)

    exact_path = TESTS / 'uploaded_seed_189_exact_metadata.json'
    baseline_path = TESTS / 'uploaded_seed_189_baseline_replay.json'
    corrected_path = TESTS / 'uploaded_seed_1810_corrected_replay.json'
    exact, baseline, corrected = map(read, (exact_path, baseline_path, corrected_path))
    assert exact['status'] == 'exactly_reproduced' and exact['matching_placements'] == 4036
    assert exact['mismatched_placements'] == 0
    assert baseline['goal_met'] and baseline['sphere_sizes_match_original']
    assert baseline['checked_network_locations'] == 4036
    for audit in (baseline, corrected):
        assert audit['status'] == 'audit_completed' and audit['source_unchanged_during_run']
        assert audit['exact_reproduction_sha256'] == sha(exact_path)
        assert audit['audit_script_sha256'] == sha(TESTS / 'replay_uploaded_seed_1810.py')
        assert audit['mapping_entries'] == 719
        assert audit['all_network_placements_restored_exactly']
        assert audit['all_network_item_classifications_restored_exactly']
        assert audit['all_shop_prices_restored_exactly']
    assert corrected['world_version'] == '1.8.10' and not corrected['goal_met']
    assert corrected['checked_network_locations'] == 355 and corrected['blocked_network_locations'] == 3681
    assert corrected['focused_items']['Triforce Piece']['collected'] == 3
    for name, digest in corrected['source_sha256'].items():
        assert sha(SOURCE / name) == digest, (name, 'stale corrected seed audit')
        source_bindings += 1
    frontier_path = TESTS / 'uploaded_seed_1810_frontier_explanation.json'
    diagnostic_path = TESTS / 'uploaded_seed_1810_blocker_diagnostic.json'
    frontier, diagnostic = map(read, (frontier_path, diagnostic_path))
    assert frontier['status'] == 'existing_seed_fails_corrected_rules'
    assert diagnostic['status'] == 'diagnosed' and diagnostic['source_unchanged_during_run']
    for evidence in (frontier, diagnostic):
        assert not evidence['goal_met'] and evidence['checked_network_locations'] == 355
        assert evidence['blocked_network_locations'] == 3681
    assert frontier['triforce_pieces'] == diagnostic['actual_triforce_pieces_at_stop'] == 3
    assert frontier['required_triforce_pieces'] == diagnostic['required_triforce_pieces'] == 20
    assert frontier['script_sha256'] == sha(TESTS / 'summarize_uploaded_seed_1810_frontier.py')
    assert diagnostic['diagnostic_script_sha256'] == sha(TESTS / 'diagnose_uploaded_seed_1810.py')
    for field in ('input_sha256', 'proof_source_sha256'):
        for relative, digest in frontier[field].items():
            assert sha(ROOT / relative) == digest, (frontier_path.name, relative)
            other_bindings += 1
    for relative, digest in diagnostic['source_sha256'].items():
        assert sha(SOURCE / relative) == digest, (diagnostic_path.name, relative)
        source_bindings += 1
    diagnostic_replay_path = Path(diagnostic['replay_report'])
    assert diagnostic_replay_path == TESTS / 'uploaded_seed_1810_diagnostic_replay.json'
    assert sha(diagnostic_replay_path) == diagnostic['replay_report_sha256']
    diagnostic_replay = read(diagnostic_replay_path)
    assert diagnostic_replay['exact_reproduction_sha256'] == sha(exact_path)
    assert diagnostic_replay['audit_script_sha256'] == sha(TESTS / 'replay_uploaded_seed_1810.py')
    assert not diagnostic_replay['goal_met'] and diagnostic_replay['checked_network_locations'] == 355
    assert diagnostic_replay['source_sha256'] == corrected['source_sha256']
    assert frontier['smallest_concrete_lost_approach']['lost_progression']['item'] == 'Pot Soul'
    assert frontier['preserved_valid_opening']['open_chest_sphere'] == 8
    assert frontier['preserved_valid_opening']['scale_sphere'] == 9
    inputs = validation / 'inputs'
    inputs.mkdir(exist_ok=True)
    shutil.copyfile(original_yaml, inputs / 'SOH-EXTREME-original.yaml')
    spoiler = ROOT / 'upload/AP_90569625277056890789_Spoiler(1).txt'
    assert sha(spoiler) == exact['spoiler_sha256']
    shutil.copyfile(spoiler, inputs / 'AP_90569625277056890789_Spoiler.txt')
    for path in (exact_path, baseline_path, corrected_path, frontier_path,
                 diagnostic_path, diagnostic_replay_path,
                 TESTS / 'uploaded_seed_189_exact_reproduction.json',
                 TESTS / 'reported_seed_187_reproduction.json'):
        shutil.copyfile(path, inputs / path.name)
    reference_sources = {}
    for original, copied in (
        ('tests/uploaded_seed_189_baseline/source/archipelago/soh_extreme/EnemyRoomGraph.json',
         'reference_sources/1.8.9_EnemyRoomGraph.json'),
        ('source/src/overlays/actors/ovl_Bg_Mizu_Water/z_bg_mizu_water.h',
         'reference_sources/z_bg_mizu_water.h'),
    ):
        expected = frontier['input_sha256'].get(original, frontier['proof_source_sha256'].get(original))
        assert expected == sha(ROOT / original), original
        destination = inputs / copied
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / original, destination)
        assert sha(destination) == expected
        reference_sources[original] = {'archive_path': 'validation/inputs/' + copied, 'sha256': expected}
    (inputs / 'reference_sources/INDEX.json').write_text(json.dumps(reference_sources, indent=2) + '\n')
    for name in ('audit_uploaded_seed_189.py', 'replay_uploaded_seed_1810.py',
                 'seed_safety_1810_run_full_fill.py', 'seed_safety_1810_regressions.py',
                 'seed_safety_1810_source_build_check.py', 'finder_hints_186_validate_apworld.py',
                 'diagnose_uploaded_seed_1810.py', 'summarize_uploaded_seed_1810_frontier.py',
                 'entrance_184_source_build_probe.ps1', 'finalize_seed_safety_1810_delivery.py'):
        shutil.copyfile(TESTS / name, validation / name)
    shutil.copyfile(ROOT / 'prepare_seed_safety_1810_delivery.py',
                    validation / 'prepare_seed_safety_1810_delivery.py')
    (inputs / 'SCOPE.txt').write_text(
        'The 1.8.9 metadata report exactly reproduces the user upload with immutable 1.8.9 sources.\n'
        'The baseline replay matches all 36 original progression sphere sizes.\n'
        'The corrected 1.8.10 replay intentionally FAILS the unchanged old seed goal.\n'
        'Its 355 reachable checks and 3/20 goal pieces demonstrate why this seed needs regeneration.\n'
        'The 1.8.7 report is historical input for the retained Jabu source-rule regression.\n'
        'Fresh 1.8.10 generation evidence is separate, in the parent validation directory.\n')
    count = len(sources)
    delta = len(completeness['changed_since_1.8.9'])
    summary = {
        'status': 'passed', 'version': '1.8.10', 'utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Current release tests and source/archive verification. The old uploaded seed fails the corrected logic audit.',
        'complete_replacement_source_files': count, 'changed_since_1.8.9': delta,
        'source_sha256': sources, 'apworld_sha256': apworld_sha,
        'manifest_sha256': sha(manifest_path), 'yaml_sha256': sha(PACKAGE / 'SOH-EXTREME.yaml'),
        'verified_report_source_bindings': source_bindings,
        'verified_fixture_and_input_bindings': other_bindings,
        'copied_reference_sources': reference_sources,
        'current_reports': recorded, 'fresh_full_fills': fills,
        'uploaded_seed_audit': {
            'output_name': exact['official_output_name'], 'internal_seed': exact['seed'],
            'exact_placements': 4036, 'entrance_map_entries': 719,
            'original_baseline_goal_met': True, 'baseline_sphere_sizes_match_original': True,
            'corrected_goal_met': False, 'corrected_reachable_checks': 355,
            'corrected_blocked_checks': 3681, 'goal_pieces_reachable': 3, 'goal_pieces_required': 20,
            'new_seed_required': True, 'unchanged_old_server_placements': True,
            'exact_reproduction_sha256': sha(exact_path),
            'baseline_replay_sha256': sha(baseline_path), 'corrected_replay_sha256': sha(corrected_path),
            'frontier_explanation_sha256': sha(frontier_path),
            'blocker_diagnostic_sha256': sha(diagnostic_path),
            'diagnostic_replay_sha256': sha(diagnostic_replay_path),
            'lost_approach': frontier['smallest_concrete_lost_approach'],
            'preserved_valid_opening': frontier['preserved_valid_opening'],
        },
        'limitations': [
            'The uploaded source snapshot lacks the root CMake project, full native dependencies and extracted ROM collision assets.',
            'No complete Windows game build, live AP session, controller/ImGui run or in-game playthrough was performed.',
            'Native fixtures execute production bodies with documented engine I/O shims; they do not recreate full scene geometry.',
            'The two fresh full fills validate these configurations and seeds under the corrected AP rules, not every possible physical route or seed.',
            'Old item/server placements are unchanged by a client update; this uploaded seed must be regenerated.',
            'Historical 1.8.9 validation is retained as provenance and is distinct from current 1.8.10 evidence.',
        ],
    }
    (validation / 'seed_safety_1810_release_validation.json').write_text(json.dumps(summary, indent=2) + '\n')
    readme = fr"""SOH-EXTREME 1.8.10 - Complete replacement source files
====================================================

This single cumulative ZIP contains {count} complete replacement source files,
the matching soh_extreme.apworld, YAML and revision 4 clean-build helpers.
All previous 1.8.9 replacement source files are retained. {delta} files changed
or were added since 1.8.9. Merge soh\, src\, archipelago\ and tools\ into your
existing complete checkout. These are complete files, with no patch to apply.

UPLOADED SEED 90569625277056890789: REGENERATION REQUIRED
------------------------------------------------------
The original 1.8.9 seed was exactly reproduced: all 4,036 item placements,
719 entrance connections and all 36 original progression sphere sizes match.
The audit also restored original item classifications and all 104 shop prices.

With those same placements/map under the corrected 1.8.10 access rules,
progression stops after 355/4,036 checks and 3/20 required Triforce Pieces.
The remaining 3,681 checks and the goal are inaccessible under these rules.
The dry Water Low Emblem Open Chest doorway and the first Swim/Scale pickup
remain reachable; the lock happens later, before access to Pot Soul.

The old solver admitted two flooded middle-floor Water Temple arrivals and
assumed water-control capability that this inventory had not established.
After the first Scale, those assumptions opened a route through Water's
upper exit, Death Mountain Trail and Spirit Temple's statue platform into
the GTG Lobby. That made the GTG Lobby -> Sand Room doorway's Pot Soul appear
reachable in the original sphere 11. The corrected rules reject the flooded
approach; they do not impose the destination's hazard on a source-door check.

Installing the client update cannot relocate the old server's placed items.
Generate a fresh seed using the enclosed APWorld.

WATER, AGE AND DOOR LOGIC
-------------------------
Reviewed flooded Water Temple room arrivals require usable Iron Boots.
Usable boots include the actual age requirement and Swim. Dry upper ledges,
the dry 3F Iron Boots pickup and proven dry-floor drops retain their routes.

A mixed doorway applies both its physical source rule and its landing hazard
to graph traversal. The source crossing check still uses its own physical
requirements: a later water recovery does not erase an already crossed check.

With room doors shuffled, reaching the real Low/Middle control action is
required to establish those levels. Middle cannot be played while submerged.
High retains the native capability proved at the actual High Emblem.
Vanilla aggregate paths can no longer bypass shuffled pillar doorways.
Legitimate local pillar swimming/floating routes remain represented.

Nine submerged enemy checks receive local water/combat requirements:
four GTG underwater Shell Blades and five Water Temple Shell Blades.
Dry doors and other checks in those rooms do not inherit an unrelated enemy's
underwater condition. GTG underwater checks include Song of Time, usable
Iron Boots/Hookshot and the required water timer.

GERUDO GUARDS AND VINES
-----------------------
Both Gerudo vine ascents require Climb or a usable Hookshot in AP, matching
the native rules. Child Link cannot substitute an unusable adult Hookshot.

Loaded Gerudo guards now apply a received membership card before their next
hostile sensing/capture action, including the first NPC Soul restored update.
Automatic capture cancellation only releases that guard's own message and
cutscene. KO/stuns, friendly roles and voluntary jail travel are preserved.

In the uploaded map the Zora's Domain exit lands directly above GTG. The two
screenshot door checks therefore do not imply a ground-patrol approach.
They do not get a blanket membership-card requirement. The absence of NPC
Soul does not grant permanent logical permission to cross guarded routes.

RICHARD'S DELIVERY ROUTE
------------------------
Market at night -> Back Alley -> Dog Lady's House stays connected.
The house entrance and return remain checks but are excluded from entrance
shuffle; the Market/Back Alley connection remains fixed as well.

Delivery requires child/night access, the configured Dog/Animal Soul,
NPC Soul and Hylian speech requirements, plus the house key/Skeleton Key
when locks are enabled. Native tests confirm Richard's identity survives
the normal delivery route and the correct turn-in grants the check.
An unrelated scene without the dog object can lose the follower, which is
why the local carrier route is preserved. Normal following distance applies.

ROOM RETURN AND DEATH
----------------------
Return to Previous Scene restores the immediate prior room's departure
point at the doorway. This includes two rooms within the same dungeon scene
and actual same-room transitions through different shuffled doorways.

Death with entrance shuffle active reloads the current room at its recorded
arrival checkpoint and preserves the previous-room destination. It does not
replace that destination with the death/reload. A -> B, death in B, return
still goes to the source doorway in A. Reloads and canceled room preloads are not
successful crossings.

The menu selection policy is preserved: Go to Dungeon Spawn remains the
manual action for ordinary dungeons and dungeon-only/unmixed pools.
Return to Previous Scene is used when room doors are mixed with an enabled
outside category. Return to Spawn still uses the seed's resolved age spawn.
Recovery/return reloads do not award extra transition checks or rerandomize
an already resolved destination.

PREVIOUS FEATURES RETAINED
--------------------------
Coupled entrances, overworld options, enabled-only mixed All, random child
and adult spawns, experimental entrance labels, dungeon-only pool partitions,
individual-song note selection, descriptive Finder names, scene grouping and
dropdown behavior, optional room/door numbers, paged hints and AP progression
hint sharing remain included. Earlier invisible NPC/object, Lost Woods Mido,
Jabu tentacle/carried-Ruto, trial-medallion and scene-switch fixes are retained.

INSTALL AND BUILD
-----------------
1. Close the game. Merge this ZIP's root folders into the complete checkout,
   replacing the corresponding files. Put BUILD_RELEASE.cmd/.ps1 and
   SOURCE_FILES.json in that checkout's root as well.
2. From Command Prompt run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   Use your actual checkout/build paths if different. The helper verifies
   every replacement source and performs:
   cmake --build build-vs --config Release --parallel 8 --clean-first
   Launch the executable whose path the helper prints.
3. Install the enclosed soh_extreme.apworld into:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Update the generator and tracker installations if they are separate,
   then restart them. Generator, tracker and native client must be 1.8.10.
4. Generate a fresh seed. The original YAML setting values/weights are kept;
   the bundled YAML includes the explicit song_note_songs: [all] selector.

VALIDATION AND LIMITS
---------------------
Fresh child seed 181001 and adult seed 181002 both passed complete official
Archipelago 0.6.8 generation, the goal and 4,036/4,036 checks under current rules.
These are generation regression results, not new playable seed output files.
The official APWorld ZIP loader verified all 120 package files and all release
version markers. Current native/AP test reports and source hashes are included
under validation/. See VALIDATION.txt for the executed suite counts and scope.

This environment cannot build the complete Windows game from the partial
uploaded checkout. Native tests compile production function bodies with
documented engine I/O shims. Full scene collision/actor assets, a live game
playthrough and visual confirmation of doorway positioning are not available.
"""
    (PACKAGE / 'README.txt').write_text(readme, encoding='utf-8')
    lines = [
        'SOH-EXTREME 1.8.10 current validation',
        '==================================',
        '',
        'Release checks: PASSED. The old uploaded seed: FAILED corrected logic; regenerate.',
        f'Complete source files: {count}; files changed/added since 1.8.9: {delta}.',
        f'Current source/test hash bindings verified: {source_bindings}.',
        f'Fixture/input bindings verified: {other_bindings}.',
        '',
    ]
    for name, data in loaded.items():
        counts = ', '.join(f'{key}={data[key]}' for key in
                           ('case_count', 'cases', 'assertions', 'test_methods',
                            'behavior_decisions', 'test_cases', 'tests_run')
                           if key in data and not isinstance(data[key], (dict, list)))
        lines.append(f'{name}: PASSED' + ('; ' + counts if counts else ''))
    lines += ['', 'Exact old seed audit: original 4,036/4,036 and 36 matching spheres;',
              'corrected 355/4,036 and 3/20 goal pieces, goal unreachable.', '', 'LIMITS:']
    lines += ['- ' + text for text in summary['limitations']]
    (PACKAGE / 'VALIDATION.txt').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'status': 'passed', 'version': '1.8.10',
                      'source_files': count, 'current_reports': len(loaded),
                      'uploaded_seed_goal_met': False, 'fresh_full_fill_goals_met': True}))


if __name__ == '__main__':
    main()
