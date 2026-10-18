"""Observe the delivered 1.8.2 spawn placement without changing source or RNG.

Runs only through connect_entrances in official AP 0.6.7. On a placement
failure, optionally searches the otherwise untouched target list to establish
whether the 50 random proposals missed a legal destination.
"""
import argparse
import hashlib
import json
import random
import time
import traceback
from collections import Counter
from pathlib import Path

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

import yaml
import Utils
from BaseClasses import CollectionState
from Generate import roll_settings
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--age', choices=('child', 'adult'), required=True)
    parser.add_argument('--diagnose-untried', action='store_true')
    parser.add_argument('--current-source', action='store_true', help='Use current source instead of frozen 1.8.2 module.')
    parser.add_argument('--yaml', type=Path, default=Path('/workspace/scratch/8fddab5b8169/delivery/SOH-EXTREME-1.8.2-overworld-entrances/SOH-EXTREME.yaml'))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    er_path = Path(ER.__file__)
    if not args.current_source:
        er_path = Path('/workspace/scratch/8fddab5b8169/delivery/SOH-EXTREME-1.8.2-overworld-entrances/payload/archipelago/soh_extreme/EntranceRandomizer.py')
        er_source = er_path.read_bytes()
        assert hashlib.sha256(er_source).hexdigest() == 'f69c936c6a12d237158b3aff28d8d36f98e2901d5d42ef8689a1e713a800396b'
        exec(compile(er_source, str(er_path), 'exec'), ER.__dict__)
    random.seed(args.seed)
    rolled = roll_settings(yaml.safe_load(args.yaml.read_text()))
    options = {name: getattr(rolled, name).value for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value for name, value in options.items()}
    options['starting_age'] = args.age
    started = time.monotonic()
    report = {
        'seed': args.seed, 'starting_age': args.age, 'archipelago_version': Utils.__version__,
        'world_version': SohExtremeWorld.world_version.as_simple_string(),
        'yaml': str(args.yaml), 'yaml_sha256': hashlib.sha256(args.yaml.read_bytes()).hexdigest(),
        'entrance_randomizer_sha256': hashlib.sha256(er_path.read_bytes()).hexdigest(),
        'entrance_randomizer_source': str(er_path),
        'options': options, 'stages': [], 'one_way_trials': [],
        'scope': 'Official AP setup through connect_entrances only; no full item fill or native gameplay.',
    }
    original_place = ER._place_one_way
    original_candidate = ER._candidate
    original_start = ER._starting_state_is_viable
    active = None

    def observed_candidate(world):
        candidate = original_candidate(world)
        if active is not None:
            target = candidate[active['source_id']]
            active['trials'].append({'target_id': target, 'target': ER.ENDPOINTS[target]['name'],
                                     'default_spawn': ER._is_default_spawn(ER.ENDPOINTS[active['source_id']], target)})
        return candidate

    def observed_start(world, mapping, edges, fill_locations):
        result = original_start(world, mapping, edges, fill_locations)
        if active is not None and active.get('current') is not None:
            active['current']['starting_state_viable'] = bool(result)
        return result

    def observed_place(world, mapping, source, viable, **kwargs):
        nonlocal active
        row = {'source_id': source['id'], 'source': source['name'], 'category': source['category'], 'trials': []}
        active = row
        started_place = time.monotonic()

        def observed_viable(candidate):
            target = candidate[source['id']]
            if (not row['trials'] or row['trials'][-1]['target_id'] != target
                    or 'fully_viable' in row['trials'][-1]):
                row['trials'].append({'target_id': target, 'target': ER.ENDPOINTS[target]['name'],
                                      'default_spawn': ER._is_default_spawn(source, target)})
            row['current'] = row['trials'][-1]
            result = viable(candidate)
            row['current']['fully_viable'] = bool(result)
            row['current'] = None
            return result

        try:
            result = original_place(world, mapping, source, observed_viable, **kwargs)
            row['status'] = 'accepted' if result is not None else 'kept_original'
            row['result_id'] = result[source['id']] if result is not None else mapping[source['id']]
            return result
        except Exception as exc:
            row['status'] = 'failed'
            row['exception'] = f'{type(exc).__name__}: {exc}'
            row['unique_proposals'] = len({trial['target_id'] for trial in row['trials']})
            row['proposed_categories'] = dict(Counter(ER.ENDPOINTS[trial['target_id']]['category'] for trial in row['trials']))
            row['all_target_count'] = len(ER._one_way_targets(world, source))
            row['failure_mapping'] = {str(k): v for k, v in mapping.items()}
            if args.diagnose_untried:
                tested = {trial['target_id'] for trial in row['trials']}
                row['untried_diagnostic'] = []
                for target in ER._one_way_targets(world, source):
                    if target['id'] in tested or ER._is_default_spawn(source, target['id']):
                        continue
                    current = {'target_id': target['id'], 'target': target['name']}
                    row['current'] = current
                    candidate = dict(mapping)
                    candidate[source['id']] = target['id']
                    current['fully_viable'] = bool(viable(candidate))
                    row['untried_diagnostic'].append(current)
                    row['current'] = None
                    if current['fully_viable']:
                        row['missed_playable_alternate'] = current
                        break
            raise
        finally:
            row.pop('current', None)
            row['elapsed_seconds'] = round(time.monotonic() - started_place, 3)
            report['one_way_trials'].append(row)
            active = None

    ER._candidate = observed_candidate
    ER._place_one_way = observed_place
    ER._starting_state_is_viable = observed_start
    try:
        multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=args.seed, options=options)
        world = multiworld.worlds[1]
        for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules', 'connect_entrances'):
            print(f'{args.seed} {args.age}: {stage}', flush=True)
            stage_started = time.monotonic()
            call_all(multiworld, stage)
            report['stages'].append({'name': stage, 'elapsed_seconds': round(time.monotonic()-stage_started, 3)})
            print(f'{args.seed} {args.age}: {stage} completed at {time.monotonic()-started:.2f}s', flush=True)
        report['status'] = 'passed'
        report['mapping_endpoints'] = len(world._er_mapping)
        report['spawn_targets'] = {str(source): {'target_id': world._er_mapping.get(source, source),
                                               'target': ER.ENDPOINTS[world._er_mapping.get(source, source)]['name']}
                                   for source in (187, 642)}
        eligible = {row['id'] for row in ER._eligible(world)}
        mapping = {source: target for source, target in world._er_mapping.items() if source in eligible}
        ER.validate_mapping(world, mapping)
        report['coupled_mapping_validation'] = 'passed'
        report['enabled_categories'] = sorted(ER.enabled_categories(world))
        report['raw_mixed_categories'] = sorted(world.options.mixed_entrance_pools.value)
        report['expanded_mixed_categories'] = sorted(ER.mixed_categories(world))
        report['overworld_endpoints'] = sum(ER.ENDPOINTS[source]['category'] == 'overworld' for source in mapping)
        report['changed_overworld_endpoints'] = sum(ER.ENDPOINTS[source]['category'] == 'overworld' and source != target
                                                   for source, target in mapping.items())
        report['nondefault_spawns'] = all(not ER._is_default_spawn(ER.ENDPOINTS[source], mapping[source])
                                         for source in (187, 642) if source in mapping)
        initial = CollectionState(multiworld)
        initial.sweep_for_advancements(locations=[loc for loc in world.get_locations()
                                                  if loc.item is not None and loc.item.player == world.player])
        initial_checks = [loc for loc in world.get_locations()
                          if loc.address is not None and ER._reachable_at_starting_age(world, initial, loc)]
        report['initial_checks'] = len(initial_checks)
        report['initial_check_examples'] = [loc.name for loc in initial_checks[:12]]
    except Exception as exc:
        report['status'] = 'failed'
        report['exception'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
    finally:
        ER._candidate = original_candidate
        ER._place_one_way = original_place
        ER._starting_state_is_viable = original_start
        report['entrance_randomizer_sha256_after_run'] = hashlib.sha256(er_path.read_bytes()).hexdigest()
        report['source_unchanged_during_run'] = report['entrance_randomizer_sha256'] == report['entrance_randomizer_sha256_after_run']
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        args.report.write_text(json.dumps(report, indent=2, default=lambda value: sorted(value) if isinstance(value, set) else str(value))+'\n')
        summary = {key: report[key] for key in ('seed', 'starting_age', 'status', 'elapsed_seconds')}
        summary['one_way_placement'] = [{key: row[key] for key in ('source_id', 'category', 'status', 'result_id', 'unique_proposals', 'missed_playable_alternate') if key in row}
                                      for row in report['one_way_trials']]
        if 'exception' in report:
            summary['exception'] = report['exception']
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
