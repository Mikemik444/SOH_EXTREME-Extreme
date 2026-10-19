"""Bind current executed evidence to the complete cumulative 1.8.9 source."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
TESTS = ROOT / 'tests'
PACKAGE = ROOT / 'delivery/SOH-EXTREME-1.8.9-source-files'
REQUIRED = {
    'souls_restart_189_soul_npc_native.json',
    'souls_restart_189_soul_object_native.json',
    'souls_restart_189_npc_logic.json',
    'souls_restart_189_npc_native_logic.json',
    'souls_restart_189_lost_woods_mido.json',
    'souls_restart_189_dungeon_pools.json',
    'souls_restart_189_restart_native.json',
    'souls_restart_189_spawn_lifecycle.json',
    'souls_restart_189_song_selection.json',
    'souls_restart_189_song_notes_native.json',
    'souls_restart_189_regressions.json',
    'souls_restart_189_full_fill_adult.json',
    'souls_restart_189_full_fill_child_subset.json',
    'souls_restart_189_apworld_validation.json',
    'souls_restart_189_version_validation.json',
    'souls_restart_189_source_build_validation.json',
    'souls_restart_189_source_completeness.json',
}
PROBES = {
    'souls_restart_189_npc_logic.json': 'tools/tests/validate_npc_path_blockers.py',
    'souls_restart_189_dungeon_pools.json': 'tools/tests/test_dungeon_door_pools.py',
    'souls_restart_189_npc_native_logic.json': 'tools/tests/test_soul_logic_native.py',
    'souls_restart_189_lost_woods_mido.json': 'tools/tests/test_lost_woods_mido.py',
}
TEMPLATES = {
    'souls_restart_189_npc_native_logic.json': 'tools/tests/soul_object_validation/logic_fixture.cpp.in',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = PACKAGE / 'SOURCE_FILES.json'
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest['version'] == '1.8.9'
    expected = {row['path']: row['sha256'] for row in manifest['files']}
    for name, digest in expected.items():
        assert sha(SOURCE / name) == digest == sha(PACKAGE / name), name
    validation = PACKAGE / 'validation'
    validation.mkdir(exist_ok=True)
    report_paths = {p.name: p for p in TESTS.glob('souls_restart_189_*.json')
                    if not p.name.endswith(('_source_zip_validation.json', '_release_validation.json'))}
    assert REQUIRED <= report_paths.keys(), sorted(REQUIRED - report_paths.keys())
    loaded, reports = {}, {}
    verified, auxiliary_verified = 0, 0
    for name, path in sorted(report_paths.items()):
        data = json.loads(path.read_bytes())
        status = data.get('status', data.get('passed'))
        assert status is True or isinstance(status, str) and status.startswith('passed'), (name, status)
        for field in ('source_sha256', 'source_hashes', 'sources', 'test_sha256'):
            for relative, digest in data.get(field, {}).items():
                assert isinstance(digest, str) and len(digest) == 64, (name, field, relative)
                assert sha(SOURCE / relative) == digest, (name, relative, 'stale source/test binding')
                verified += 1
        for field in ('dependency_sha256', 'header_hashes', 'native_header_hashes'):
            for relative, digest in data.get(field, {}).items():
                assert sha(TESTS / 'entrance_184_native_dependencies' / relative) == digest, (name, relative)
                auxiliary_verified += 1
        for relative, digest in data.get('fixture_sha256', {}).items():
            assert sha(ROOT / relative) == digest, (name, relative)
            auxiliary_verified += 1
        for relative, digest in data.get('input_sha256', {}).items():
            assert sha(ROOT / relative) == digest, (name, relative)
            auxiliary_verified += 1
        if name in PROBES:
            assert sha(SOURCE / PROBES[name]) == data['probe_sha256'], name
            auxiliary_verified += 1
        if name in TEMPLATES:
            assert sha(SOURCE / TEMPLATES[name]) == data['template_sha256'], name
            auxiliary_verified += 1
        if name == 'souls_restart_189_lost_woods_mido.json':
            assert sha(SOURCE / 'tools/tests/validate_npc_path_blockers.py') == data['shared_probe_sha256']
            auxiliary_verified += 1
        loaded[name] = data
        reports[name] = {'status': status, 'sha256': sha(path), 'scope': data.get('scope')}
        shutil.copyfile(path, validation / name)

    completeness = loaded['souls_restart_189_source_completeness.json']
    assert completeness['source_sha256'] == expected
    assert completeness['all_previous_replacement_files_retained']
    apworld_sha = sha(PACKAGE / 'soh_extreme.apworld')
    for name in ('souls_restart_189_apworld_validation.json', 'souls_restart_189_version_validation.json'):
        assert loaded[name]['archive_sha256'] == apworld_sha
    build = loaded['souls_restart_189_source_build_validation.json']
    assert build['manifest_sha256'] == sha(manifest_path)
    assert build['apworld_sha256'] == apworld_sha
    for name, digest in build['helper_sha256'].items():
        assert sha(PACKAGE / name) == digest
    original_yaml_sha = sha(ROOT / 'upload/SOH-EXTREME(20261017-230302).yaml')
    assert original_yaml_sha == '30af887663cd55d0408176a9b5f23b3ee25eb0ff9098ea10ace0c749811128f5'
    assert completeness['original_yaml_sha256'] == original_yaml_sha
    yaml_sha = sha(PACKAGE / 'SOH-EXTREME.yaml')
    assert completeness['yaml_sha256'] == yaml_sha

    runtime_path = TESTS / 'archipelago_068_runtime_provenance.json'
    runtime = json.loads(runtime_path.read_bytes())
    assert runtime['version'] == '0.6.8' and runtime['missing_prior_files'] == []
    for relative, digest in runtime['source_hashes'].items():
        assert sha(ROOT / 'ap-runtime-068' / relative) == digest, relative
        auxiliary_verified += 1
    shutil.copyfile(runtime_path, validation / runtime_path.name)
    for name in (
        'souls_restart_189_run_full_fill.py', 'souls_restart_189_regressions.py',
        'souls_restart_189_child_subset.yaml', 'finder_hints_186_validate_apworld.py',
        'souls_restart_189_source_build_check.py', 'entrance_184_source_build_probe.ps1',
        'finalize_souls_restart_189_delivery.py',
    ):
        shutil.copyfile(TESTS / name, validation / name)
    shutil.copyfile(ROOT / 'prepare_souls_restart_189_delivery.py',
                    validation / 'prepare_souls_restart_189_delivery.py')
    inputs = validation / 'inputs'
    inputs.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'upload/SOH-EXTREME(20261017-230302).yaml',
                    inputs / 'SOH-EXTREME-original.yaml')
    shutil.copyfile(TESTS / 'reported_seed_187_reproduction.json',
                    inputs / 'reported_seed_187_reproduction.json')
    (inputs / 'SCOPE.txt').write_text(
        'The original YAML is the exact user configuration used by the adult full fill and NPC probes.\n'
        'The 1.8.7 reproduction JSON is historical map/input evidence for the current saved-map\n'
        'restoration regression. It is not a passing generation report for 1.8.9.\n')

    fills = {}
    for case in ('adult', 'child_subset'):
        data = loaded[f'souls_restart_189_full_fill_{case}.json']
        player = data['validation']['players']['1']
        assert data['archipelago_version'] == '0.6.8' and data['world_version'] == '1.8.9'
        assert data['source_unchanged_during_run']
        assert player['goal_met'] and player['checked'] == player['network_checks']
        assert data['initial_hyrule_field_reachable'] and data['saved_mixed_entrance_pools'] == ['all']
        input_path = ROOT / ('upload/SOH-EXTREME(20261017-230302).yaml' if case == 'adult'
                             else 'tests/souls_restart_189_child_subset.yaml')
        assert data['yaml_sha256'] == sha(input_path)
        hint = data['hint_generation'][-1]
        assert hint['song_note_mask'] == (0xFFF if case == 'adult' else 0x81)
        assert hint['entrance_pool_policy_revision'] == 1 and hint['dungeon_door_mixed_outside'] == 1
        fills[case] = {
            'seed': data['seed'], 'starting_age': data['age'],
            'network_checks': player['network_checks'], 'goal_met': True,
            'initial_network_checks': data['initial_network_checks'],
            'initial_physical_checks': data['initial_physical_checks'],
            'initial_hyrule_field_reachable': True,
            'child_spawn': data['child_spawn'], 'adult_spawn': data['adult_spawn'],
            'changed_overworld_endpoints': data['changed_overworld_endpoints'],
            'selected_individual_note_songs': hint['selected_individual_note_songs'],
            'song_item_placements': hint['song_item_placements'], 'hint_kinds': hint['hint_rows_by_kind'],
            'yaml_sha256': data['yaml_sha256'],
        }
    count = len(expected)
    delta_count = len(completeness['changed_since_1.8.8'])
    summary = {
        'status': 'passed', 'version': '1.8.9', 'utc': datetime.now(timezone.utc).isoformat(),
        'layout': 'complete_source_files', 'complete_replacement_source_files': count,
        'changed_or_added_since_1.8.8': delta_count, 'source_sha256': expected,
        'apworld_sha256': apworld_sha, 'yaml_sha256': yaml_sha,
        'original_yaml_sha256': original_yaml_sha, 'yaml_change': completeness['yaml_change'],
        'manifest_sha256': sha(manifest_path), 'build_helpers_sha256': build['helper_sha256'],
        'verified_report_source_hash_entries': verified,
        'verified_fixture_and_runtime_hash_entries': auxiliary_verified,
        'current_reports': reports, 'full_fills': fills,
        'limitations': [
            'The uploaded snapshot lacks the root CMake project, full native dependencies, and extracted ROM collision assets.',
            'No complete Windows game build, live AP session, ImGui session, or in-game playthrough was performed.',
            'Native fixtures compile production function bodies with explicit engine I/O and geometric shims; their reports define their exact scope.',
            'The monotonic AP model conservatively retains ordinary progression gates for routes that could close when NPC Soul arrives remotely.',
            'Two complete fills validate these configurations and seeds under the AP logic model, not every possible seed or physical route.',
            'Previously generated server placements are unchanged by a client update; new options and corrected generation rules require a fresh seed.',
            'Validation under previous_1.8.8 is historical provenance, distinct from current executed reports.',
        ],
    }
    (validation / 'souls_restart_189_release_validation.json').write_text(json.dumps(summary, indent=2) + '\n')
    readme = fr"""SOH-EXTREME 1.8.9 - Complete replacement source files
====================================================

This cumulative ZIP contains {count} complete replacement source files and the
matching soh_extreme.apworld. All previous 1.8.8 replacement files are retained.
Merge the root directories soh\, src\, archipelago\ and tools\ into your
existing complete checkout. {delta_count} files changed or were added since 1.8.8.

INVISIBLE NPCS AND OBJECT COLLISION
----------------------------------
NPCs without NPC Soul cannot talk, auto-talk, exchange or give items, be
carried, be targeted, or accept the Lost Woods Mido ocarina interaction.
Two precise placements retain hidden blocking movement and solid collision:
  - The Kokiri Forest exit boy (En_Ko, type 3, in Kokiri Forest).
  - Adult Mido in Lost Woods, where he blocks the route to the meadow.
Mido in Kokiri Forest and all other missing-soul NPC placements are non-solid.
Acquiring the appropriate Soul restores the existing actors' normal behavior.

Missing Crate Soul: small and large crates are invisible and non-solid.
Missing Rock / Boulder Soul: regular small rocks are invisible and non-solid.
Large silver rocks, brown/bronze boulders, and ceiling boulders stay solid.
All missing-soul crates, rocks and boulders remain unusable and unbreakable.

When NPC Soul is shuffled, AP and Finder require it for every conversation,
including path blockers. Adult Mido's ordinary Lost Woods passage requires
usable Saria's Song in both directions, plus NPC Soul and Kokiri speech when
their respective shuffle options are enabled. Child passage and the existing
enabled backflip alternative keep
their original requirements. Other temporary passages opened by absent NPCs
remain conservatively out of logic where receiving Soul could close them.

DUNGEON POOLS AND RETURN ACTIONS
-------------------------------
Unmixed dungeon room doors shuffle within each individual dungeon. This also
covers forward-only dungeon shutters. Normal two-way doors retain a paired
return, and the six Jabu carried-Ruto door pairs retain native connections.

Go to Dungeon Spawn returns to the physical dungeon entrance. This is the
default dungeon action with no entrance shuffle, separate dungeon/room-door
shuffle, separate boss shuffle, or a mixed pool containing only dungeon
categories. A shuffled boss uses the dungeon from which Link entered it.
The resolved dungeon entrance is not shuffled a second time.

Return to Previous Scene is used when enabled dungeon_doors is in the actual
mixed pool with an enabled outside category. All includes enabled categories
only. Mixing unrelated pools, listing a disabled category, or selecting only
dungeon_doors does not activate this mode. Dungeon categories are dungeons,
bosses and dungeon_doors; the remaining categories count as outside.

Previous Scene restores the last distinct playable scene and its recorded
entry context. Same-scene room changes do not overwrite that scene history.
It does not copy temporary switches between scenes. A fresh randomized spawn
with no prior scene offers Continue and Return to Spawn until history exists.
Game-over follows the available dungeon/history return with safe spawn fallback.

Return to Spawn remains a separate action using the seed's assigned spawn for
the chosen age. It clears a queued scene return. Same-save reloads retain the
entrance map and tracker context; changing save, age or map invalidates unsafe
pending returns. Reconnecting does not reroll saved entrance mappings.

SELECT WHICH SONGS USE INDIVIDUAL NOTES
--------------------------------------
The new Song Note Songs option chooses which songs become Progressive items.
Unselected songs remain complete songs and follow Shuffle Songs: anywhere,
song locations, dungeon rewards, or their vanilla locations when off.

The included SOH-EXTREME.yaml preserves every original setting value and weight
and adds the following default, which keeps the previous all-song behavior:

  song_note_shuffle: individual_notes
  song_note_songs:
    - all

To split only two songs, replace the song_note_songs list with:

  song_note_songs:
    - zeldas_lullaby
    - bolero_of_fire

Accepted song keys:
  zeldas_lullaby       eponas_song          sarias_song
  suns_song           song_of_time        song_of_storms
  minuet_of_forest     bolero_of_fire      serenade_of_water
  requiem_of_spirit    nocturne_of_shadow  prelude_of_light

Full names such as Zelda's Lullaby also work. All overrides other listed songs.
An empty list splits none. With Song Note Shuffle off, the list is ignored.
Most songs need 6 copies; Bolero needs 8, Serenade 5, and Nocturne 7.
All uses the existing 74 copies and existing item/save identities. The native
tracker shows only selected songs in the note-progress section and sums their
required copies. Starting with a selected song grants its complete note group;
starting with an unselected song grants its ordinary whole-song item. Ocarina
and shuffled button requirements still apply. Older saved note seeds default
to all when they do not contain the new selection field.
New seeds convert numbered legacy notes in selected starting-song requests
to matching Progressive copies. Selected-song plando must also use Progressive
copies; overlapping numbered and progressive receipts are rejected. Existing
UT saves retain their original receipt identities.

CUMULATIVE FEATURES RETAINED
---------------------------
Paired entrance returns, overworld shuffle, all-enabled mixed pools, assigned
child/adult spawns, reviewed age-safe destinations, trial medallion and Jabu
tentacle barriers, room-switch logic, Finder names/collapse preferences,
paged hints, AP progressive item hints, Way of the Hero/barren hints, and
tracker continuity remain included. Entrance randomizer settings remain
Experimental. The current NPC/collision rules above replace earlier behavior.

INSTALL AND BUILD
-----------------
1. Close the game and finish any active build.
2. Extract into E:\test\bb\, merging directories and replacing included files.
   Keep your full checkout, root CMakeLists.txt and configured build-vs folder.
3. From E:\test\bb, run:
     BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"
   The helper reports version 1.8.9, revision 4, and verifies all {count} source
   files before the configured clean build:
     cmake --build build-vs --config Release --parallel 8 --clean-first
   Wait for success, then launch the exact executable path printed by the helper.
4. Install the top-level soh_extreme.apworld at:
     C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Update generation and tracker installations if separate, then restart them.
5. Generate a fresh seed and create its matching AP save/server slot. Updated
   source cannot relocate progression in an already generated server.
6. Confirm version 1.8.9 under Network -> Archipelago and inspect the applied
   entrance map plus child/adult spawn destinations.

VALIDATION AND PRACTICAL LIMITS
-------------------------------
Current reports include actual AP pools/prefill/song rules, NPC interaction
rules, both Mido directions, room/trial/Jabu regressions, native actor and
collision functions, native save/scene return routing, song receipt/tracker
functions, the built APWorld loader, and the shipped build helper preflight.

Two complete official Archipelago 0.6.8 fills reached every network check and
the goal: the original all-song configuration as adult, and a clearly labeled
child variant selecting Zelda's Lullaby and Bolero only. Both retained initial
physical checks and Hyrule Field access. Final hints did not change placements
or RNG state. Exact seeds, counts, source hashes, and report scopes are in
VALIDATION.txt and validation\souls_restart_189_release_validation.json.

The supplied source snapshot is incomplete for a full Windows game build or
playthrough. Native fixtures isolate engine I/O and lack extracted ROM
collision assets. Rebuild the complete checkout for in-game verification.
The passing fills validate these seeds under the AP model, not every possible
seed or physical route. Reports under previous_1.8.8 are historical evidence.
"""
    (PACKAGE / 'README.txt').write_text(readme, encoding='utf-8')
    notes = [
        'SOH-EXTREME 1.8.9 - Current validation evidence and limits',
        '=' * 59, '',
        f'Complete replacement source files: {count}; changed/added since 1.8.8: {delta_count}.',
        f'Verified current report/source/test bindings: {verified}.',
        f'Verified fixture/runtime bindings: {auxiliary_verified}.',
        'The release JSON records every report and source SHA-256.', '',
    ]
    for name, data in loaded.items():
        counts = {key: data[key] for key in ('cases', 'test_cases', 'tests_run', 'assertions', 'native') if key in data}
        notes.extend((name, '  Result: passed' + ('; ' + json.dumps(counts) if counts else ''),
                      '  Scope: ' + str(data.get('scope', 'See the full report.')), ''))
    notes.extend(('COMPLETE OFFICIAL FILLS', json.dumps(fills, indent=2), '', 'LIMITATIONS'))
    notes.extend('- ' + line for line in summary['limitations'])
    (PACKAGE / 'VALIDATION.txt').write_text('\n'.join(notes) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'source_files': count, 'delta_files': delta_count,
                      'current_reports': len(reports), 'verified_source_bindings': verified,
                      'verified_auxiliary_bindings': auxiliary_verified, 'full_fills': fills}, indent=2))


if __name__ == '__main__':
    main()
