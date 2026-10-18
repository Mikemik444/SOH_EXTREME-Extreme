"""Validate descriptive names, legacy aliases, physical IDs and AP rule behavior.

Run with official Archipelago source and dependencies on PYTHONPATH. An optional
pre-change capture compares the complete constructed graph and reachability by
numeric ID; names are the only permitted difference.
"""

import argparse
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

import yaml
from BaseClasses import CollectionState, PlandoOptions
from Generate import roll_settings
from Options import ExcludeLocations, PriorityLocations, StartLocationHints
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld, SceneTransitions
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme.CheckDescriptions import (
    CHECK_DESCRIPTIONS, CHECK_NAME_ALIASES, canonical_location_name,
    normalize_location_options, shuffled_check_label,
)
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages


ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'archipelago/soh_extreme'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('yaml_path', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    generator = ROOT / 'tools/generate_check_descriptions.py'
    subprocess.run([sys.executable, str(generator), '--check'], check=True)
    spec = importlib.util.spec_from_file_location('check_description_generator', generator)
    generated = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generated)
    assert generated.build_descriptions() == CHECK_DESCRIPTIONS

    # Every physical field, gate and address remains the original catalog value.
    original_enemies = generated.constructor_rows(WORLD / 'EnemyDropLocations.py', 'EnemyDropLocationData')
    assert len(original_enemies) == len(ENEMY_DROP_LOCATIONS)
    for raw, current in zip(original_enemies, ENEMY_DROP_LOCATIONS):
        assert raw[1:] == dataclasses.astuple(current)[1:]
        assert current.name == CHECK_DESCRIPTIONS[current.address]['name']
    original_transitions = [row for filename in ('SceneTransitionCatalog.json', 'DungeonDoorCatalog.json')
                            for row in json.loads((WORLD / filename).read_text())]
    assert len(original_transitions) == len(SceneTransitions.CATALOG)
    for raw, current in zip(original_transitions, SceneTransitions.CATALOG):
        assert {k: v for k, v in raw.items() if k != 'name'} == {
            k: v for k, v in current.items() if k != 'name'}
        assert current['name'] == CHECK_DESCRIPTIONS[current['id']]['name']

    names = SohExtremeWorld.location_name_to_id
    assert len(names) == len(set(names.values()))
    for identity, row in CHECK_DESCRIPTIONS.items():
        assert names[row['name']] == identity
        assert canonical_location_name(row['legacy_name']) == row['name']
    for legacy, canonical in CHECK_NAME_ALIASES.items():
        assert legacy not in names
        assert SohExtremeWorld.location_name_groups[legacy] == {canonical}
    # Standard AP YAML validation expands singleton legacy-name groups.
    for option_class in (ExcludeLocations, PriorityLocations, StartLocationHints):
        option = option_class(set(CHECK_NAME_ALIASES))
        option.verify(SohExtremeWorld, 'Descriptive check validation', PlandoOptions.none)
        assert option.value == set(CHECK_NAME_ALIASES.values())
    datapackage = SohExtremeWorld.get_data_package_data()
    assert datapackage['location_name_to_id'] == names
    assert len({identity: name for name, identity in names.items()}) == len(names)

    # A shuffled arrival keeps its destination dungeon even when the physical
    # passage label shows that dungeon just once.
    door_endpoints = [row for row in ER.ENDPOINTS.values()
                      if row.get('check_id') in CHECK_DESCRIPTIONS
                      and CHECK_DESCRIPTIONS[row['check_id']]['kind'] == 'door']
    for source in door_endpoints:
        assert shuffled_check_label(source, source) == CHECK_DESCRIPTIONS[source['check_id']]['name']
        destination = next(row for row in door_endpoints if row['source_scene'] != source['source_scene'])
        label = shuffled_check_label(source, destination)
        target = CHECK_DESCRIPTIONS[destination['check_id']]
        assert label == CHECK_DESCRIPTIONS[source['check_id']]['name'] + ' | Shuffled to: ' + target['arrival_name']

    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    if baseline:
        assert set(names.values()) == set(baseline['datapackage'].values())
        for old_name, identity in baseline['datapackage'].items():
            assert names[canonical_location_name(old_name)] == identity
    random.seed(1)
    rolled = roll_settings(yaml.safe_load(args.yaml_path.read_text()))
    options = {name: getattr(rolled, name).value for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value for name, value in options.items()}
    ages = {}
    for starting_age in ('child', 'adult'):
        mw = setup_multiworld(SohExtremeWorld, steps=(), seed=1, options=dict(options, starting_age=starting_age))
        world = mw.worlds[1]
        # Saved UT snapshots bypass YAML verification. Normalize their sets,
        # then restore the user's options before constructing the real world.
        original = set(world.options.exclude_locations.value)
        world.options.exclude_locations.value = set(CHECK_NAME_ALIASES)
        normalize_location_options(world.options)
        assert world.options.exclude_locations.value == set(CHECK_NAME_ALIASES.values())
        world.options.exclude_locations.value = original
        for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
            call_all(mw, stage)
        locations = sorted((loc for loc in world.get_locations() if loc.address is not None), key=lambda loc: loc.address)
        assert len(locations) == len({loc.address for loc in locations})
        lookup_count = 0
        for loc in locations:
            description = CHECK_DESCRIPTIONS.get(loc.address)
            if description:
                assert world.get_location(description['legacy_name']) is loc
                assert world.get_location(description['name']) is loc
                lookup_count += 1
        physical = {str(loc.address): {
            'name': loc.name, 'parent': loc.parent_region.name, 'rule': type(loc.access_rule).__qualname__,
            'items': sorted(loc.access_rule.item_dependencies()) if hasattr(loc.access_rule, 'item_dependencies') else [],
            'regions': sorted(loc.access_rule.region_dependencies()) if hasattr(loc.access_rule, 'region_dependencies') else [],
        } for loc in locations}
        cases = {}
        for label, items in (
            ('actual_start', None),
            ('sword_and_souls', ('Kokiri Sword', 'Master Sword', 'Keese Soul', 'Deku Baba Soul', 'Skulltula Soul', 'Jabu Jabu Tentacle Soul')),
            ('mobility', ('Climb', 'Grab / Power Bracelet', 'Progressive Scale', 'Progressive Scale', 'Progressive Hookshot', 'Progressive Hookshot', 'Crawl', 'Shovel', 'Roll', 'Speak Zora', 'NPC Soul', 'Open Chest')),
            ('all', None),
        ):
            state = mw.get_all_state(False) if label == 'all' else CollectionState(mw)
            if items:
                for name in items:
                    state.collect(world.create_item(name), True)
            if label != 'all':
                state.sweep_for_advancements(locations=[loc for loc in world.get_locations() if loc.item is not None and loc.item.player == 1])
            for age in (Ages.CHILD, Ages.ADULT):
                state._soh_extreme_age[1] = age
                cases[label + ':' + age.name] = [loc.address for loc in locations if loc.can_reach_as_age(state, age)]
        changed = None
        if baseline:
            before = baseline['ages'][starting_age]
            assert physical.keys() == before['locations'].keys()
            for identity, record in physical.items():
                assert {k: v for k, v in record.items() if k != 'name'} == {
                    k: v for k, v in before['locations'][identity].items() if k != 'name'}
            assert cases == before['cases']
            changed = sum(record['name'] != before['locations'][identity]['name'] for identity, record in physical.items())
        ages[starting_age] = {'network_checks_before_er': len(locations), 'legacy_and_canonical_lookups': lookup_count,
                             'renamed_active_checks': changed, 'reachable_checks_by_case': {key: len(value) for key, value in cases.items()},
                             'physical_rules_and_reachability_match_baseline': bool(baseline)}
        print(starting_age, ages[starting_age], flush=True)

    report = {
        'status': 'passed', 'archipelago_version': '0.6.7', 'world_version': world.world_version.as_simple_string(),
        'canonical_datapackage_locations': len(names), 'unique_numeric_ids': len(set(names.values())),
        'shared_descriptions': len(CHECK_DESCRIPTIONS), 'legacy_aliases': len(CHECK_NAME_ALIASES),
        'physical_enemy_rows_unchanged': len(original_enemies), 'physical_transition_rows_unchanged': len(original_transitions),
        'option_alias_classes': ['ExcludeLocations', 'PriorityLocations', 'StartLocationHints'],
        'shuffle_arrivals_tested': len(door_endpoints), 'ages': ages,
        'baseline': str(args.baseline) if args.baseline else None,
        'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None,
        'source_sha256': {path.relative_to(WORLD).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in WORLD.rglob('*') if path.is_file() and path.suffix in ('.py', '.json')},
    }
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'report': str(args.report)}), flush=True)


if __name__ == '__main__':
    main()
