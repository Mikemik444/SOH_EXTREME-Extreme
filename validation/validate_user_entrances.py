"""Run the supplied weighted YAML through AP 0.6.7 and validate its entrance graph."""
import argparse
import json
import random
import time
from pathlib import Path

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

import yaml
from BaseClasses import CollectionState
from Generate import roll_settings
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--age', choices=('child', 'adult'), required=True)
    parser.add_argument('--seed', type=int, default=1801)
    parser.add_argument('--yaml', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--fixed-spawns', '--pairs-only', dest='fixed_spawns', action='store_true')
    args = parser.parse_args()
    root = Path('/workspace/scratch/8fddab5b8169')
    random.seed(args.seed)
    yaml_path = args.yaml or (root / 'upload/SOH-EXTREME(20261017-171802).yaml')
    weights = yaml.safe_load(yaml_path.read_text())
    rolled = roll_settings(weights)
    options = {name: getattr(rolled, name).value for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value for name, value in options.items()}
    options['starting_age'] = args.age
    if args.fixed_spawns:
        options['shuffle_child_spawn'] = 0
        options['shuffle_adult_spawn'] = 0
    start = time.monotonic()
    multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=args.seed, options=options)
    world = multiworld.worlds[1]
    for step in ('generate_early', 'create_regions', 'create_items', 'set_rules', 'connect_entrances'):
        print(f'{args.age}: {step}', flush=True)
        call_all(multiworld, step)
        print(f'{args.age}: {step} finished at {time.monotonic()-start:.1f}s', flush=True)
    initial = CollectionState(multiworld)
    initial.sweep_for_advancements(locations=[loc for loc in world.get_locations()
                                              if loc.item is not None and loc.item.player == world.player])
    checks = [loc for loc in world.get_locations()
              if loc.address is not None and ER._reachable_at_starting_age(world, initial, loc)]
    rows = ER._eligible(world)
    mapping = {key: value for key, value in world._er_mapping.items()
               if key in {row['id'] for row in rows}}
    ER.validate_mapping(world, mapping)
    edges = {int(edge.name.removeprefix('EXTREME Shuffled Entrance ')): edge
             for region in world.get_regions() for edge in region.exits
             if edge.name.startswith('EXTREME Shuffled Entrance ')}
    fill_locations = [loc for loc in world.get_locations() if loc.address is not None and loc.item is None]
    assert ER._starting_state_is_viable(world, mapping, edges, fill_locations)
    result = {
        'yaml': str(yaml_path),
        'age': world.options.starting_age.current_key, 'seed': args.seed, 'fixed_spawns': args.fixed_spawns,
        'elapsed_seconds': round(time.monotonic()-start, 2),
        'mapping_endpoints': len(mapping), 'accepted_swaps': world._er_generation_attempts,
        'initial_checks': len(checks), 'initial_check_examples': [loc.name for loc in checks[:12]],
        'child_spawn': ER.ENDPOINTS[world._er_mapping.get(187, 187)]['name'],
        'adult_spawn': ER.ENDPOINTS[world._er_mapping.get(642, 642)]['name'],
        'enabled_entrance_categories': sorted(ER.enabled_categories(world)),
        'raw_mixed_entrance_pools': sorted(world.options.mixed_entrance_pools.value),
        'expanded_mixed_categories': sorted(ER.mixed_categories(world)),
        'overworld_endpoints': sum(row['category'] == 'overworld' for row in rows),
        'changed_overworld_endpoints': sum(row['category'] == 'overworld' and mapping[row['id']] != row['id']
                                           for row in rows),
        'overworld_examples': [{'source_id': source, 'source': ER.ENDPOINTS[source]['name'],
                                'target_id': mapping.get(source, source),
                                'target': ER.ENDPOINTS[mapping.get(source, source)]['name']}
                               for source in (333, 441, 327, 445, 582, 449, 1250, 1238)],
    }
    name = f'entrance_validation_{args.age}' + ('_fixed_spawns' if args.fixed_spawns else '')
    report = args.report or (root / 'tests' / (name + '.json'))
    report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
