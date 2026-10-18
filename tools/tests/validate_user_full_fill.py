"""Validate a SOH-EXTREME YAML using the complete official Archipelago fill.

Run with Archipelago source and its dependencies on PYTHONPATH. The current
SOH-EXTREME source must be installed in that source tree's worlds directory.
No ROM, server upload, client connection, or user save is opened.
"""
import argparse
import json
import logging
import random
import time
from pathlib import Path

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

import Utils
import yaml
from BaseClasses import CollectionState, PlandoOptions
from Generate import roll_settings
from Main import main as generate
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('yaml_path', type=Path)
    parser.add_argument('--age', choices=('child', 'adult'), default='child')
    parser.add_argument('--seed', type=int, default=1801)
    parser.add_argument('--report', type=Path)
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    random.seed(options.seed)
    rolled = roll_settings(yaml.safe_load(options.yaml_path.read_text()))
    age_class = SohExtremeWorld.options_dataclass.type_hints['starting_age']
    rolled.starting_age = age_class.from_any(options.age)
    args = argparse.Namespace(**{name: {1: value} for name, value in vars(rolled).items()})
    args.multi = 1
    args.outputpath = None
    args.outputname = f'entrance-regression-{options.seed}'
    args.race = False
    args.plando = PlandoOptions.bosses
    args.sprite = {}
    args.sprite_pool = {}
    args.csv_output = False
    args.skip_output = True
    args.spoiler_only = False
    args.skip_prog_balancing = False
    # Keep AP's normal swap fallback; never grant items to rescue a failed fill.
    settings.get_settings().generator.panic_method = 'swap'
    start = time.monotonic()
    multiworld = generate(args, seed=options.seed)
    world = multiworld.worlds[1]
    rows = ER._eligible(world)
    eligible = {row['id'] for row in rows}
    mapping = {source: target for source, target in world._er_mapping.items() if source in eligible}
    ER.validate_mapping(world, mapping)
    slot_data = world.fill_slot_data()
    assert slot_data['extreme_all_options']['mixed_entrance_pools'] == sorted(world.options.mixed_entrance_pools.value)
    assert slot_data['entrance_randomizer']['connections'] == {str(k): v for k, v in world._er_mapping.items()}
    native = slot_data['extreme_soh_cvars']
    for source in (187, 642):
        if source in world._er_mapping:
            assert native['EntranceMap.' + str(source)] == world._er_mapping[source]
    validation = multiworld._soh_final_validation
    assert validation['passed'] and validation['players'][1]['goal_met']
    assert validation['players'][1]['checked'] == validation['players'][1]['network_checks']
    initial = CollectionState(multiworld)
    initial.sweep_for_advancements(locations=[loc for loc in world.get_locations() if loc.address is None])
    first_checks = [loc for loc in world.get_locations()
                    if loc.address is not None and ER._reachable_at_starting_age(world, initial, loc)]
    first_progression = [{'location': loc.name, 'item': loc.item.name}
                         for loc in first_checks if loc.item and loc.item.advancement]
    result = {
        'archipelago_version': Utils.__version__,
        'world_version': world.world_version.as_simple_string(),
        'yaml': str(options.yaml_path),
        'seed': options.seed, 'age': world.options.starting_age.current_key,
        'elapsed_seconds': round(time.monotonic() - start, 2),
        'initial_network_checks': len(first_checks),
        'initial_physical_checks': sum(loc.parent_region.name != str(Regions.ROOT) for loc in first_checks),
        'initial_hyrule_field_reachable': ER._reachable_at_starting_age(
            world, initial, world.get_region(str(Regions.HYRULE_FIELD))),
        'precollected_items': [item.name for item in multiworld.precollected_items[world.player]],
        'initial_progression_checks': first_progression,
        'child_spawn': ER.ENDPOINTS[world._er_mapping.get(187, 187)]['name'],
        'adult_spawn': ER.ENDPOINTS[world._er_mapping.get(642, 642)]['name'],
        'enabled_entrance_categories': sorted(ER.enabled_categories(world)),
        'saved_mixed_entrance_pools': slot_data['extreme_all_options']['mixed_entrance_pools'],
        'expanded_mixed_categories': sorted(ER.mixed_categories(world)),
        'native_overworld_flag': native['ShuffleOverworldEntrances'],
        'exported_spawn_destinations': {str(source): native.get('EntranceMap.' + str(source))
                                       for source in (187, 642)},
        'mapping_endpoints': len(mapping),
        'accepted_swaps': world._er_generation_attempts,
        'overworld_endpoints': sum(row['category'] == 'overworld' for row in rows),
        'changed_overworld_endpoints': sum(row['category'] == 'overworld' and mapping[row['id']] != row['id']
                                           for row in rows),
        'overworld_examples': [{'source_id': source, 'source': ER.ENDPOINTS[source]['name'],
                                'target_id': mapping.get(source, source),
                                'target': ER.ENDPOINTS[mapping.get(source, source)]['name']}
                               for source in (333, 441, 327, 445, 582, 449, 1250, 1238)],
        'validation': validation,
        'scope': 'Official Main.main through pre_output with full restrictive fill; no native gameplay run.',
    }
    serialized = json.dumps(result, indent=2) + '\n'
    if options.report:
        options.report.write_text(serialized)
    print(serialized, flush=True)


if __name__ == '__main__':
    main()
