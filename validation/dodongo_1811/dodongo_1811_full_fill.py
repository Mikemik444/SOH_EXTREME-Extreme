"""Validate a fresh 1.8.11 full fill with the reported seed's resolved options.

The input spoiler's placements/map are not preserved here; their unchanged
replay is a separate audit. No files are sent to a server or user save.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import random
import time

from audit_uploaded_seed_189 import options_from_spoiler, source_hashes
import settings
import Utils
from BaseClasses import CollectionState, PlandoOptions
from Main import main as generate
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spoiler', type=Path, required=True)
    parser.add_argument('--exact-reproduction', type=Path, required=True)
    parser.add_argument('--age', choices=('child', 'adult'), required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--initial-time-random', action='store_true')
    parser.add_argument('--closed-forest-off', action='store_true',
                        help='Explicit adult-test variant: Closed Forest On otherwise forces Child.')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    evidence = json.loads(args.exact_reproduction.read_bytes())
    assert evidence['status'] == 'exactly_reproduced'
    assert evidence['matching_placements'] == 4036 and not evidence['mismatched_placements']
    assert hashlib.sha256(args.spoiler.read_bytes()).hexdigest() == evidence['spoiler_sha256']
    text = args.spoiler.read_text(encoding='utf-8-sig')
    options, verified, hidden = options_from_spoiler(text)
    option_overrides = {}
    options['starting_age'] = type(options['starting_age']).from_any(args.age)
    if args.closed_forest_off:
        assert args.age == 'adult', 'The open-forest override is only for the explicit adult test.'
        option_overrides['closed_forest'] = {
            'original': options['closed_forest'].current_option_name, 'requested': 'Off',
            'reason': 'Closed Forest On forces a child start; use Off to test an actual adult start.'}
        options['closed_forest'] = type(options['closed_forest']).from_any('off')
    if args.initial_time_random:
        options['frozen_starting_time'] = type(options['frozen_starting_time']).from_any(0)
    before = source_hashes()
    assert SohExtremeWorld.world_version.as_simple_string() == '1.8.11'
    generation = argparse.Namespace(**{name: {1: option} for name, option in options.items()})
    generation.game = {1: 'SOH-EXTREME'}
    generation.name = {1: 'mikemik44'}
    generation.multi = 1
    generation.outputpath = None
    generation.outputname = str(random.Random(args.seed).randint(0, 10**20 - 1)).zfill(20)
    generation.race = False
    generation.plando = PlandoOptions.connections | PlandoOptions.texts | PlandoOptions.bosses
    generation.sprite = {}
    generation.sprite_pool = {}
    generation.csv_output = False
    generation.skip_output = True
    generation.spoiler_only = False
    generation.skip_prog_balancing = False
    settings.get_settings().generator.panic_method = 'swap'
    start = time.monotonic()
    mw = generate(generation, seed=args.seed)
    world = mw.worlds[1]
    resolved_age = world.options.starting_age.current_option_name.casefold()
    assert resolved_age == args.age, (
        f'Requested {args.age} start was adjusted to {resolved_age}; this run does not cover the requested age.')
    if args.closed_forest_off:
        assert world.options.closed_forest.current_option_name.casefold() == 'off'
    validation = mw._soh_final_validation
    player = validation['players'][1]
    assert validation['passed'] and player['goal_met']
    assert player['checked'] == player['network_checks'] == 4036
    eligible = {row['id'] for row in ER._eligible(world)}
    ER.validate_mapping(world, {source: target for source, target in world._er_mapping.items()
                                if source in eligible})
    state = CollectionState(mw)
    state.sweep_for_advancements(locations=[loc for loc in world.get_locations() if loc.address is None])
    first = [loc for loc in world.get_locations() if loc.address is not None and
             ER._reachable_at_starting_age(world, state, loc)]
    first_physical = [loc for loc in first if loc.parent_region.name != str(Regions.ROOT)]
    progression = [loc for loc in first_physical if loc.item and loc.item.advancement]
    field = ER._reachable_at_starting_age(world, state, world.get_region(str(Regions.HYRULE_FIELD)))
    assert first_physical and progression and field
    assert before == source_hashes(), 'APWorld source changed during full-fill validation'
    original_mapping = {int(source): target for source, target in evidence['mapping'].items()}
    report = {
        'status': 'passed', 'kind': 'fresh_full_fill_with_reported_options',
        'version': '1.8.11', 'archipelago_version': Utils.__version__,
        'seed': args.seed, 'age': resolved_age, 'requested_age': args.age,
        'resolved_age_matches_requested': True, 'option_overrides': option_overrides,
        'elapsed_seconds': round(time.monotonic() - start, 2),
        'spoiler_sha256': evidence['spoiler_sha256'],
        'original_exact_reproduction_sha256': hashlib.sha256(args.exact_reproduction.read_bytes()).hexdigest(),
        'source_sha256': before, 'source_unchanged_during_run': True,
        'fixture_sha256': {Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           'audit_uploaded_seed_189.py': hashlib.sha256(Path(__file__).with_name('audit_uploaded_seed_189.py').read_bytes()).hexdigest()},
        'resolved_options': {name: getattr(world.options, name).current_option_name for name in verified},
        'non_spoiler_defaults': hidden, 'initial_time_random_restored': args.initial_time_random,
        'starting_items': [item.name for item in mw.precollected_items[1]],
        'initial_physical_checks': len(first_physical), 'initial_hyrule_field_reachable': field,
        'initial_progression': [{'id': loc.address, 'name': loc.name, 'item': loc.item.name} for loc in progression],
        'child_spawn': {'id': world._er_mapping[187], **ER.ENDPOINTS[world._er_mapping[187]]},
        'adult_spawn': {'id': world._er_mapping[642], **ER.ENDPOINTS[world._er_mapping[642]]},
        'mapping_entries': len(world._er_mapping),
        'mapping_differs_from_uploaded_seed': original_mapping != world._er_mapping,
        'validation': validation,
        'scope': 'Official Archipelago Main full restrictive fill and production final validation. Starting age/inventory has a physical path to Hyrule Field and a non-Menu progression check. Fresh generation, not a repaired old map; no native gameplay run or output files.',
    }
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'seed', 'age', 'elapsed_seconds',
                                                  'initial_physical_checks', 'initial_hyrule_field_reachable')}), flush=True)


if __name__ == '__main__':
    main()
