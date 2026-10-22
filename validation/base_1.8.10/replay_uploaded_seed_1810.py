"""Replay an exactly recovered entrance map and the user's unchanged placements.

This is a rule-model audit, not a new fill and not a native gameplay test.
The baseline report must first prove every network placement matches the
uploaded spoiler. Native event locations are rebuilt from the selected source;
all addressed items and any vanilla shop items come from the uploaded spoiler.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import logging
from pathlib import Path
import time

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import Utils
from BaseClasses import CollectionState, Item, ItemClassification
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
import worlds.soh_extreme as package
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme.FrontierFill import validate_final_multiworld
from worlds.soh_extreme._vendor_oot_soh.Enums import Items, Locations
from worlds.soh_extreme._vendor_oot_soh.ShopItems import vanilla_shop_prices
from Fill import FillError


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    directory = Path(package.__file__).resolve().parent
    return {'archipelago/soh_extreme/' + path.relative_to(directory).as_posix(): sha(path)
            for path in sorted(directory.rglob('*'))
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}


def placement_lines(text, names):
    result, unmatched = {}, []
    for line in text.split('Locations:\n', 1)[1].split('Playthrough:\n', 1)[0].splitlines():
        if not line:
            continue
        matches = []
        offset = 0
        while (position := line.find(': ', offset)) != -1:
            name = line[:position]
            if name in names:
                matches.append((name, line[position + 2:]))
            offset = position + 2
        assert len(matches) <= 1, (line, matches)
        if matches:
            name, item = matches[0]
            assert name not in result, name
            result[name] = item
        else:
            unmatched.append(line)
    return result, unmatched


def location_row(loc):
    return {'id': loc.address, 'name': loc.name, 'region': loc.parent_region.name,
            'item': loc.item.name if loc.item else None,
            'progression': bool(loc.item and loc.item.advancement)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spoiler', type=Path, required=True)
    parser.add_argument('--exact-reproduction', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    started = time.monotonic()
    evidence = json.loads(args.exact_reproduction.read_bytes())
    assert evidence['status'] == 'exactly_reproduced'
    assert evidence['all_placements_match_uploaded_spoiler']
    assert evidence['matching_placements'] == evidence['network_checks'] == 4036
    assert evidence['mismatched_placements'] == 0
    assert sha(args.spoiler) == evidence['spoiler_sha256']
    assert 'placements' in evidence and 'shop_prices' in evidence, (
        'The exact reproduction must include item classifications and shop prices; '
        'a spoiler alone does not preserve useful versus progression Skull Tokens.')
    original_network = {row['id']: row for row in evidence['placements'] if row['id'] is not None}
    assert len(original_network) == evidence['network_checks']
    options = {name: row['value'] for name, row in evidence['resolved_options'].items()}
    assert set(options) == set(SohExtremeWorld.options_dataclass.type_hints)
    if evidence['initial_time_random_restored']:
        options['frozen_starting_time'] = 0
    before = source_hashes()
    mw = setup_multiworld(SohExtremeWorld, steps=(), seed=evidence['seed'], options=options)
    mw.player_name[1] = 'mikemik44'
    mw.seed_name = evidence['official_output_name']
    for step in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        print(step, flush=True)
        call_all(mw, step)
    world = mw.worlds[1]
    actual = {key: getattr(world.options, key).current_option_name
              for key in evidence['resolved_options']}
    assert actual == {key: row['display_value'] for key, row in evidence['resolved_options'].items()}
    world.using_ut = True
    world.passthrough = {'song_note_catalog_revision': 1, 'entrance_randomizer': {
        'revision': ER.REVISION,
        'destination_policy_revision': ER.Safety.POLICY_REVISION,
        'pool_policy_revision': ER.POOL_POLICY_REVISION,
        'connections': evidence['mapping'],
    }}
    ER.connect(world)
    assert world._er_mapping == {int(key): value for key, value in evidence['mapping'].items()}
    # ER.connect above exercises the saved-map restore branch. The original
    # rules then prune optional local actions using the actual full inventory.
    # Prefill's addressed rewards are overwritten from the uploaded spoiler.
    world.using_ut = False
    world.passthrough = {}
    for step in ('generate_basic', 'pre_fill'):
        print(step, flush=True)
        call_all(mw, step)
    text = args.spoiler.read_text(encoding='utf-8-sig')
    locations = world.get_locations()
    listed, removed_local_lines = placement_lines(text, {loc.name for loc in locations})
    local_changes = []
    for loc in locations:
        name = listed.get(loc.name)
        if loc.address is not None:
            assert name is not None, ('Missing network placement', loc.name, loc.address)
        if loc.address is not None:
            original = original_network[loc.address]
            assert original['name'] == loc.name and original['item']['name'] == name
            item = world.create_item(name, classification=ItemClassification(original['item']['classification']))
            assert int(item.classification) == original['item']['classification']
            assert item.code == original['item']['id'] and item.player == original['item']['player']
            loc.locked = original['locked']
        else:
            if name is None or (loc.item and loc.item.name == name):
                continue
            old_item = loc.item.name if loc.item else None
            try:
                item = world.create_item(name, create_as_event=True)
            except (ValueError, KeyError):
                item = Item(name, ItemClassification.progression, None, 1)
            local_changes.append({'name': loc.name, 'prefill_item': old_item, 'spoiler_item': name})
        loc.item = item
        item.location = loc
        if name.startswith('Buy '):
            world.shop_prices[loc.name] = vanilla_shop_prices[Items(name)]
            world.shop_vanilla_items[loc.name] = name
    def location_key(name):
        try:
            return Locations(name)
        except ValueError:
            return name
    world.shop_prices = {location_key(name): value for name, value in evidence['shop_prices'].items()}
    world.shop_vanilla_items = {location_key(name): value
                               for name, value in evidence['shop_vanilla_items'].items()}
    network = [loc for loc in locations if loc.address is not None]
    assert len(network) == evidence['network_checks']
    assert all(loc.item and listed[loc.name] == loc.item.name for loc in network)
    starting = [item.name for item in mw.precollected_items[1]]
    expected_starting = [line for line in text.split('Starting Items:\n', 1)[1]
                        .split('Locations:\n', 1)[0].splitlines() if line]
    assert Counter(starting) == Counter(expected_starting) == Counter(evidence['starting_items'])
    # Follow the production validator's collection order and fixed-point loop.
    state = CollectionState(mw)
    remaining = sorted((loc for loc in locations if loc.item), key=lambda loc: (loc.player, loc.name))
    spheres, first_item_spheres = [], {}
    while remaining:
        remaining = [loc for loc in remaining
                     if loc not in state.locations_checked and loc not in state.advancements]
        sphere = [loc for loc in remaining if loc.can_reach(state)]
        if not sphere:
            break
        rows = [location_row(loc) for loc in sphere]
        number = len(spheres) + 1
        spheres.append({'sphere': number, 'checks': rows})
        for loc in sphere:
            first_item_spheres.setdefault(loc.item.name, number)
            if loc in state.locations_checked or loc in state.advancements:
                continue
            if loc.advancement:
                state.advancements.add(loc)
            state.collect(loc.item, True, loc)
    checked = [loc for loc in network
               if loc in state.locations_checked or loc in state.advancements]
    blocked = [loc for loc in network if loc not in checked]
    goal = mw.has_beaten_game(state, 1)
    try:
        validate_final_multiworld(mw)
        validation = mw._soh_final_validation
    except FillError as exc:
        validation = {'passed': False, 'error': str(exc)}
    assert validation['passed'] == (goal and not blocked)
    assert before == source_hashes(), 'Audited source changed during replay'
    focus = ('Iron Boots', 'Gerudo Membership Card', 'NPC Soul', 'Climb', 'Open Chest',
             'Progressive Scale', 'Triforce Piece', 'Time Travel', 'Rock / Boulder Soul')
    result = {
        'status': 'audit_completed', 'seed': evidence['seed'],
        'official_output_name': evidence['official_output_name'],
        'archipelago_version': Utils.__version__,
        'world_version': world.world_version.as_simple_string(),
        'source_sha256': before, 'source_unchanged_during_run': True,
        'spoiler_sha256': sha(args.spoiler), 'exact_reproduction_sha256': sha(args.exact_reproduction),
        'audit_script_sha256': sha(__file__),
        'saved_map_restored_through_production_connect': True,
        'mapping_entries': len(world._er_mapping), 'all_network_placements_restored_exactly': True,
        'all_network_item_classifications_restored_exactly': True,
        'all_shop_prices_restored_exactly': True,
        'network_checks': len(network), 'checked_network_locations': len(checked),
        'blocked_network_locations': len(blocked), 'goal_met': goal,
        'starting_items': starting, 'starting_age': world.options.starting_age.current_key,
        'starting_hearts': world.options.starting_hearts.value,
        'first_item_spheres': first_item_spheres,
        'focused_items': {name: {'collected': state.count(name, 1),
                                'placements': [dict(location_row(loc), reachable=loc in checked)
                                               for loc in network if loc.item.name == name]}
                          for name in focus},
        'blocked_checks': [location_row(loc) for loc in blocked],
        'spheres': spheres, 'production_final_validation': validation,
        'original_validation': evidence['original_ap_validation'],
        'sphere_sizes_match_original': [len(s['checks']) for s in spheres]
                                       == evidence['original_ap_validation']['sphere_sizes'],
        'local_shop_items_restored': local_changes,
        'spoiler_lines_for_removed_local_actions': removed_local_lines,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'scope': 'Exactly recovered original map and all4036 uploaded item placements, replayed under the imported source rules. No item relocation, new entrance fill, native scene collision test, or in-game playthrough.',
    }
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'world_version', 'network_checks',
                                                  'checked_network_locations', 'blocked_network_locations',
                                                  'goal_met', 'elapsed_seconds')}), flush=True)


if __name__ == '__main__':
    main()
