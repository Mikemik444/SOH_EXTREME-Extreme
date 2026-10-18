"""Validate a SOH-EXTREME YAML using the complete official Archipelago 0.6.7 fill.

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

import yaml
from BaseClasses import CollectionState, PlandoOptions
from Generate import roll_settings
from Main import main as generate
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER


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
        'archipelago_version': '0.6.7',
        'world_version': world.world_version.as_simple_string(),
        'seed': options.seed, 'age': world.options.starting_age.current_key,
        'elapsed_seconds': round(time.monotonic() - start, 2),
        'initial_network_checks': len(first_checks),
        'initial_progression_checks': first_progression,
        'child_spawn': ER.ENDPOINTS[world._er_mapping.get(187, 187)]['name'],
        'adult_spawn': ER.ENDPOINTS[world._er_mapping.get(642, 642)]['name'],
        'validation': validation,
        'scope': 'Official Main.main through pre_output with full restrictive fill; no native gameplay run.',
    }
    serialized = json.dumps(result, indent=2) + '\n'
    if options.report:
        options.report.write_text(serialized)
    print(serialized, flush=True)


if __name__ == '__main__':
    main()
