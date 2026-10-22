"""Reproduce the exact uploaded 1.8.9 seed from its resolved spoiler options.

This audit never changes production sources, installed worlds, or user saves.
The recovered map is considered exact only after all network placements match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import random
import re
import time

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import Utils
from BaseClasses import CollectionState, PlandoOptions
from Main import main as generate
from Options import OptionDict, OptionList, OptionSet, Visibility
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'


def json_value(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, dict):
        return {str(key): json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(child) for child in value]
    return value


def options_from_spoiler(text):
    header = text.split('Starting Items:', 1)[0]
    fields = {line.split(':', 1)[0].strip(): line.split(':', 1)[1].strip()
              for line in header.splitlines() if ':' in line}
    parsed, verified, defaults = {}, {}, []
    for key, cls in SohExtremeWorld.options_dataclass.type_hints.items():
        label = getattr(cls, 'display_name', key)
        expected = fields.get(label)
        if expected is None:
            assert not cls.visibility & Visibility.spoiler, (key, label, 'missing visible option')
            parsed[key] = cls.from_any(cls.default)
            defaults.append(key)
            continue
        candidates = []
        if issubclass(cls, OptionSet):
            candidates.append(set(expected.split(', ')) if expected else set())
        elif issubclass(cls, OptionList):
            candidates.append(expected.split(', ') if expected else [])
        elif issubclass(cls, OptionDict):
            assert not expected, (key, expected, 'nonempty dictionary requires explicit parser')
            candidates.append({})
        else:
            candidates.extend(dict.fromkeys(getattr(cls, 'options', {}).values()))
            if re.fullmatch(r'-?\d+', expected):
                candidates.append(int(expected))
            candidates.extend((expected, expected.lower().replace(' ', '_'), cls.default))
        matched = None
        for value in candidates:
            try:
                option = cls.from_any(value)
            except (TypeError, ValueError, KeyError, AssertionError):
                continue
            if option.current_option_name == expected:
                matched = option
                break
        assert matched is not None, (key, label, expected, cls.__name__)
        parsed[key] = matched
        verified[key] = {'display_name': label, 'display_value': expected,
                         'value': json_value(matched.value)}
    return parsed, verified, defaults


def source_hashes():
    return {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((SOURCE / 'archipelago/soh_extreme').rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def main():
    global SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spoiler', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--options-only', action='store_true')
    parser.add_argument('--source-root', type=Path, default=SOURCE)
    parser.add_argument('--initial-time-random', action='store_true',
                        help='Restore the documented input Random time before its world-RNG resolution.')
    args = parser.parse_args()
    SOURCE = args.source_root.resolve()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    text = args.spoiler.read_text(encoding='utf-8-sig')
    seed = int(re.search(r'Archipelago Version [^\n]+ -\s+Seed: (\d+)', text).group(1))
    output_name = str(random.Random(seed).randint(0, 10 ** 20 - 1)).zfill(20)
    assert output_name in args.spoiler.name, 'File name does not match the official seed name'
    options, verified, defaults = options_from_spoiler(text)
    if args.initial_time_random:
        options['frozen_starting_time'] = type(options['frozen_starting_time']).from_any(0)
    before = source_hashes()
    base = {
        'seed': seed, 'official_output_name': output_name,
        'spoiler_sha256': hashlib.sha256(args.spoiler.read_bytes()).hexdigest(),
        'archipelago_version': Utils.__version__,
        'world_version': SohExtremeWorld.world_version.as_simple_string(),
        'source_sha256': before, 'resolved_options': verified,
        'non_spoiler_options_using_defaults': defaults,
        'initial_time_random_restored': args.initial_time_random,
    }
    print(json.dumps({'stage': 'resolved_options', 'seed': seed,
                      'output_name': output_name, 'options_verified': len(verified),
                      'hidden_defaults': defaults}), flush=True)
    args.report.with_suffix('.options.json').write_text(json.dumps(base, indent=2) + '\n')
    if args.options_only:
        return
    generate_args = argparse.Namespace(**{name: {1: option} for name, option in options.items()})
    generate_args.game = {1: 'SOH-EXTREME'}
    generate_args.name = {1: 'mikemik44'}
    generate_args.multi = 1
    generate_args.outputpath = None
    generate_args.outputname = output_name
    generate_args.race = False
    generate_args.plando = PlandoOptions.connections | PlandoOptions.texts | PlandoOptions.bosses
    generate_args.sprite = {}
    generate_args.sprite_pool = {}
    generate_args.csv_output = False
    generate_args.skip_output = True
    generate_args.spoiler_only = False
    generate_args.skip_prog_balancing = False
    settings.get_settings().generator.panic_method = 'swap'
    started = time.monotonic()
    original_connect = SohExtremeWorld.connect_entrances
    original_early = SohExtremeWorld.generate_early

    def verify_resolved_options(self):
        original_early(self)
        actual = {key: getattr(self.options, key).current_option_name for key in verified}
        expected = {key: row['display_value'] for key, row in verified.items()}
        assert actual == expected, {key: [expected[key], actual[key]] for key in expected
                                   if expected[key] != actual[key]}

    def checkpoint_mapping(self):
        original_connect(self)
        checkpoint = dict(base, status='unverified_mapping_checkpoint',
                          mapping=json_value(self._er_mapping),
                          scope='Do not attribute this map to the uploaded seed until all placements match.')
        args.report.with_suffix('.mapping.json').write_text(json.dumps(checkpoint, indent=2) + '\n')
        print(json.dumps({'stage': 'entrance_map_connected', 'elapsed_seconds': round(time.monotonic()-started, 2),
                          'map_entries': len(self._er_mapping),
                          'child_spawn': ER.ENDPOINTS[self._er_mapping[187]]['name'],
                          'adult_spawn': ER.ENDPOINTS[self._er_mapping[642]]['name']}), flush=True)

    SohExtremeWorld.connect_entrances = checkpoint_mapping
    SohExtremeWorld.generate_early = verify_resolved_options
    try:
        mw = generate(generate_args, seed=seed)
    finally:
        SohExtremeWorld.connect_entrances = original_connect
        SohExtremeWorld.generate_early = original_early
    world = mw.worlds[1]
    listed = set(text.split('Locations:\n', 1)[1].split('Playthrough:\n', 1)[0].splitlines())
    locations = world.get_locations()
    network = [loc for loc in locations if loc.address is not None]
    mismatched = [{'id': loc.address, 'name': loc.name, 'generated': loc.item.name}
                  for loc in network if f'{loc.name}: {loc.item.name}' not in listed]
    initial = CollectionState(mw)
    initial.sweep_for_advancements(locations=[loc for loc in locations if loc.address is None])
    first = [loc for loc in network if ER._reachable_at_starting_age(world, initial, loc)]
    from collections import Counter
    expected_start = Counter(line for line in text.split('Starting Items:\n', 1)[1]
                             .split('Locations:\n', 1)[0].splitlines() if line)
    starting = [item.name for item in mw.precollected_items[1]]
    generated_start = Counter(starting)
    assert expected_start == generated_start, (expected_start, starting)
    after = source_hashes()
    assert before == after, 'Production sources changed during the reproduction'
    result = dict(base,
        status='exactly_reproduced' if not mismatched else 'not_exactly_reproduced',
        elapsed_seconds=round(time.monotonic()-started, 2),
        network_checks=len(network), matching_placements=len(network)-len(mismatched),
        mismatched_placements=len(mismatched), first_mismatches=mismatched[:30],
        all_placements_match_uploaded_spoiler=not mismatched,
        source_unchanged_during_run=True, starting_items=starting,
        initial_checks=[{'id': loc.address, 'name': loc.name, 'item': loc.item.name,
                         'region': loc.parent_region.name} for loc in first],
        mapping=json_value(world._er_mapping),
        placements=[{'id': loc.address, 'name': loc.name, 'region': loc.parent_region.name,
                     'locked': loc.locked,
                     'item': None if loc.item is None else {
                         'name': loc.item.name, 'id': loc.item.code,
                         'classification': int(loc.item.classification), 'player': loc.item.player}}
                    for loc in locations],
        shop_prices={str(name): value for name, value in world.shop_prices.items()},
        shop_vanilla_items={str(name): value for name, value in world.shop_vanilla_items.items()},
        disabled_entrance_actions=world._er_disabled_actions,
        child_spawn={'id': world._er_mapping[187], **ER.ENDPOINTS[world._er_mapping[187]]},
        adult_spawn={'id': world._er_mapping[642], **ER.ENDPOINTS[world._er_mapping[642]]},
        original_ap_validation=mw._soh_final_validation,
        scope='Official AP Main full fill. Exact map attribution requires all4036 placements to match; no native gameplay test.')
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'seed', 'matching_placements',
                                                 'mismatched_placements', 'elapsed_seconds')}), flush=True)


if __name__ == '__main__':
    main()
