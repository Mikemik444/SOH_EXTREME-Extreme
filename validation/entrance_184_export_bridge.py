"""Export real entrance maps for the native JSON/runtime integration harness.

Uses the supplied weighted YAML and official AP 0.6.7 generation stages through
connect_entrances, then the production fill_slot_data and AP base-type
conversion. The item pool is not filled; these files are validation fixtures,
not a playable generated seed or a replacement for the full-fill regressions.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import random
import time

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

import yaml
import Utils
from BaseClasses import CollectionState, LocationProgressType
from Generate import roll_settings
from NetUtils import convert_to_base_types
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--yaml', type=Path, required=True)
    parser.add_argument('--age', choices=('child', 'adult'), required=True)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--output-prefix', type=Path, required=True)
    args = parser.parse_args()
    package = Path(ER.__file__).parent
    before = {path.relative_to(package).as_posix(): sha256(path)
              for path in package.rglob('*')
              if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}
    random.seed(args.seed)
    weights = yaml.safe_load(args.yaml.read_text(encoding='utf-8-sig'))
    rolled = roll_settings(weights)
    options = {name: getattr(rolled, name).value
               for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value
               for name, value in options.items()}
    options['starting_age'] = args.age
    started = time.monotonic()
    multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=args.seed, options=options)
    world = multiworld.worlds[1]
    stages = []
    precollected_before_entrances = None
    for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules', 'connect_entrances'):
        print(f'{args.age}: {stage}', flush=True)
        stage_started = time.monotonic()
        call_all(multiworld, stage)
        stages.append({'name': stage, 'elapsed_seconds': round(time.monotonic() - stage_started, 3)})
        if stage == 'set_rules':
            precollected_before_entrances = Counter(item.name for item in multiworld.precollected_items[world.player])
    rows = ER._eligible(world)
    eligible = {row['id'] for row in rows}
    mapping = {source: target for source, target in world._er_mapping.items() if source in eligible}
    ER.validate_mapping(world, mapping)
    slot = world.fill_slot_data()
    # This is the same conversion Main.write_multidata uses before writing AP's
    # generated archive, followed by a JSON round-trip like the server response.
    wire_slot = json.loads(json.dumps(convert_to_base_types(slot)))
    native = wire_slot['extreme_soh_cvars']
    expected_map = {str(source): target for source, target in world._er_mapping.items()}
    assert wire_slot['entrance_randomizer']['connections'] == expected_map
    assert {key[12:]: value for key, value in native.items() if key.startswith('EntranceMap.')} == expected_map
    assert all(type(value) is int and -(2**31) <= value < 2**31 for value in native.values())
    assert native['EntranceRandomizerRevision'] == ER.REVISION == 1
    assert native['DecoupleEntrances'] == 0
    assert native['ShuffleOverworldEntrances'] == native['ShuffleOverworldSpawns'] == 1
    assert native['ShuffleDungeonDoors'] == 1
    assert wire_slot['extreme_all_options']['mixed_entrance_pools'] == ['all']
    assert ER.enabled_categories(world) == set(ER.CATEGORIES)
    assert all(world._er_mapping[endpoint] == endpoint for endpoint in ER.LOCAL_CARRIER_DOORS)
    for spawn in (187, 642):
        assert native['EntranceMap.' + str(spawn)] == world._er_mapping[spawn]
        assert not ER._is_default_spawn(ER.ENDPOINTS[spawn], world._er_mapping[spawn])

    initial_precollected = Counter(item.name for item in multiworld.precollected_items[world.player])
    assert initial_precollected == precollected_before_entrances, 'Entrance shuffle changed starting inventory'
    initial_state = CollectionState(multiworld)
    initial_state.sweep_for_advancements(locations=[loc for loc in world.get_locations()
                                                    if loc.item is not None and loc.item.player == world.player])
    swim_missing = bool(world.options.shuffle_swim.value) and not initial_state.has('Swim', world.player)
    mapped_spawns_outside_water = all(ER.ENDPOINTS[world._er_mapping[spawn]]['scene'] != 5
                                     for spawn in (187, 642) if spawn in world._er_mapping)
    assert not swim_missing or mapped_spawns_outside_water, 'An age spawn requires unavailable Swim'
    initial_hyrule_field = ER._reachable_at_starting_age(
        world, initial_state, world.get_region('Hyrule Field'))
    assert initial_hyrule_field, 'Selected shuffled spawn has no actual-inventory route to Hyrule Field'
    initial_physical_checks = sorted(
        (loc for loc in world.get_locations()
         if loc.address is not None and loc.parent_region.name != 'Menu'
         and loc.progress_type != LocationProgressType.EXCLUDED
         and ER._reachable_at_starting_age(world, initial_state, loc)),
        key=lambda loc: loc.address)
    assert initial_physical_checks

    prefix = str(args.output_prefix)
    slot_path = Path(prefix + '_slot_data.json')
    cvars_path = Path(prefix + '_cvars.json')
    report_path = Path(prefix + '_report.json')
    slot_path.write_text(json.dumps(wire_slot, sort_keys=True, indent=2) + '\n')
    # Raw callbacks receive a JSON object, not an escaped object-valued string.
    cvars_path.write_text(json.dumps(native, sort_keys=True, separators=(',', ':')) + '\n')
    after = {path.relative_to(package).as_posix(): sha256(path)
             for path in package.rglob('*')
             if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}
    assert before == after, 'Production APWorld source changed during fixture generation'
    report = {
        'status': 'passed', 'archipelago_version': Utils.__version__,
        'world_version': world.world_version.as_simple_string(),
        'yaml': str(args.yaml), 'yaml_sha256': sha256(args.yaml),
        'seed': args.seed, 'age': args.age, 'stages': stages,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'source_sha256': before, 'source_unchanged_during_run': True,
        'eligible_mapping_endpoints': len(mapping),
        'exported_mapping_endpoints': len(expected_map),
        'exported_cvars': len(native),
        'changed_overworld_endpoints': sum(row['category'] == 'overworld' and mapping[row['id']] != row['id']
                                           for row in rows),
        'enabled_categories': sorted(ER.enabled_categories(world)),
        'mixed_pools': wire_slot['extreme_all_options']['mixed_entrance_pools'],
        'initial_selected_age_hyrule_field_reachable': initial_hyrule_field,
        'initial_precollected_item_counts': dict(sorted(initial_precollected.items())),
        'precollected_unchanged_by_entrance_shuffle': True,
        'initial_swim_missing': swim_missing,
        'both_mapped_spawns_outside_water_temple': mapped_spawns_outside_water,
        'initial_reachable_physical_checks': [{'id': loc.address, 'name': loc.name}
                                            for loc in initial_physical_checks],
        'local_carrier_identity_routes': sorted(ER.LOCAL_CARRIER_DOORS),
        'spawn_destinations': {str(spawn): {'id': world._er_mapping[spawn],
                                          'name': ER.ENDPOINTS[world._er_mapping[spawn]]['name'],
                                          'scene': ER.ENDPOINTS[world._er_mapping[spawn]]['scene'],
                                          'room': ER.ENDPOINTS[world._er_mapping[spawn]].get('room')}
                               for spawn in (187, 642)},
        'artifacts': {'slot_data': {'path': str(slot_path), 'sha256': sha256(slot_path)},
                      'cvars': {'path': str(cvars_path), 'sha256': sha256(cvars_path)}},
        'scope': 'Real AP source graph and slot export through connect_entrances; no item fill or native gameplay.',
    }
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'age', 'elapsed_seconds',
                                                  'exported_mapping_endpoints', 'exported_cvars',
                                                  'changed_overworld_endpoints', 'spawn_destinations', 'artifacts')},
                     indent=2), flush=True)


if __name__ == '__main__':
    main()
