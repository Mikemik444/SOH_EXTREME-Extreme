"""Regression coverage for per-dungeon door pools and pause-return metadata.

Uses actual AP option types, reviewed endpoints, generation pool selection and
one production connect() pass. It does not place an item pool or run the game.
"""
from pathlib import Path
import argparse
import hashlib
import inspect
import json
import random
import time
import unittest

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import Utils
from Options import OptionError
from test.general import setup_multiworld
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme.NativeSettings import NATIVE_AP_DEFAULTS

ROOT = Path(__file__).resolve().parents[2]
REPORT_FACTS = {}


def world_for(**options):
    return setup_multiworld(SohExtremeWorld, steps=(), seed=18901, options=options).worlds[1]


def identity(world):
    return {row['id']: row['id'] for row in ER._eligible(world)}


def exchange_pairs(mapping, first, second):
    a, b = mapping[first], mapping[second]
    mapping[first], mapping[second] = b, a
    mapping[ER.ENDPOINTS[b]['reverse']] = ER.ENDPOINTS[first]['reverse']
    mapping[ER.ENDPOINTS[a]['reverse']] = ER.ENDPOINTS[second]['reverse']


class DungeonDoorPoolTests(unittest.TestCase):
    def assert_local(self, world, mapping):
        ER.validate_mapping(world, mapping)
        doors = 0
        for source, destination in mapping.items():
            row, target = ER.ENDPOINTS[source], ER.ENDPOINTS[destination]
            if row['category'] != 'dungeon_doors':
                continue
            doors += 1
            self.assertEqual(target['category'], 'dungeon_doors')
            self.assertEqual(row['source_scene'], target['scene'])
            if row['reverse'] >= 0:
                self.assertEqual(mapping[target['reverse']], row['reverse'])
        self.assertGreater(doors, 0)

    def test_unmixed_room_doors_stay_in_each_of_thirteen_scenes(self):
        world = world_for(shuffle_dungeon_doors=1)
        scenes = {row['source_scene'] for row in ER._eligible(world)}
        self.assertEqual(len(scenes), 13)
        for seed in range(12):
            world.random = random.Random(seed)
            mapping = ER._candidate(world)
            self.assert_local(world, mapping)
            self.assertTrue(any(source != target for source, target in mapping.items()))

    def test_enabled_other_categories_do_not_implicitly_mix_room_doors(self):
        world = world_for(shuffle_dungeon_doors=1, shuffle_overworld_entrances=1,
                          shuffle_dungeon_entrances=1, shuffle_boss_entrances=1,
                          shuffle_interior_entrances=1)
        self.assert_local(world, ER._candidate(world))

    def test_unrelated_mixed_categories_keep_room_doors_local(self):
        world = world_for(shuffle_dungeon_doors=1, shuffle_interior_entrances=1,
                          shuffle_overworld_entrances=1, mixed_entrance_pools={'overworld', 'interiors'})
        self.assert_local(world, ER._candidate(world))
        self.assertFalse(ER.dungeon_doors_mix_outside(world))
        self.assertEqual(ER.native_settings(world)['DungeonDoorMixedOutside'], 0)

    def test_singleton_door_selection_has_no_other_category_to_mix_with(self):
        for selection in ({'dungeon_doors'}, {'all'}):
            with self.subTest(selection=selection):
                world = world_for(shuffle_dungeon_doors=1, mixed_entrance_pools=selection)
                self.assert_local(world, ER._candidate(world))
                self.assertFalse(ER.dungeon_doors_are_mixed(world))
                self.assertEqual(ER.native_settings(world)['DungeonDoorMixedOutside'], 0)

    def test_disabled_mixed_category_does_not_expand_door_pool(self):
        selection = {'dungeon_doors', 'overworld', 'interiors'}
        world = world_for(shuffle_dungeon_doors=1, mixed_entrance_pools=selection)
        self.assertEqual(ER.mixed_categories(world), {'dungeon_doors'})
        self.assertEqual(world.options.mixed_entrance_pools.value, selection)
        self.assert_local(world, ER._candidate(world))
        self.assertEqual(ER.native_settings(world)['EntranceMixedPoolMask'], 1 << 10)
        self.assertEqual(ER.native_settings(world)['DungeonDoorMixedOutside'], 0)

    def test_forward_only_shutters_need_one_way_option_but_remain_local(self):
        world = world_for(shuffle_dungeon_doors=1)
        self.assertFalse(any(row['reverse'] < 0 for row in ER._eligible(world)))
        world.options.shuffle_one_way_entrances.value = 1
        shutters = [row for row in ER._eligible(world)
                    if row['category'] == 'dungeon_doors' and row['reverse'] < 0]
        self.assertEqual({row['id'] for row in shutters}, {8610, 9093, 9217, 9485, 9487})
        for source in shutters:
            targets = ER._one_way_targets(world, source)
            self.assertTrue(targets)
            self.assertEqual({row['category'] for row in targets}, {'dungeon_doors'})
            self.assertEqual({row['scene'] for row in targets}, {source['source_scene']})
            self.assertTrue(all(ER.Safety.allowed_route(source['id'], row['id']) for row in targets))
        for seed in range(8):
            world.random = random.Random(seed)
            self.assert_local(world, ER._candidate(world))
        REPORT_FACTS['forward_only_shutters'] = sorted(row['id'] for row in shutters)

    def test_ordinary_one_way_category_retains_its_own_destinations(self):
        world = world_for(shuffle_dungeon_doors=1, shuffle_one_way_entrances=1)
        source = ER.ENDPOINTS[537]
        targets = ER._one_way_targets(world, source)
        self.assertTrue(targets)
        self.assertTrue({row['category'] for row in targets} <= {'overworld', 'owls', 'warp_songs'})
        self.assertFalse(any(row['category'] == 'dungeon_doors' for row in targets))

    def test_new_unmixed_cross_dungeon_pair_is_rejected_but_legacy_is_readable(self):
        world = world_for(shuffle_dungeon_doors=1)
        source = next(row for row in ER._eligible(world) if row['primary'] and row['source_scene'] == 0)
        target = next(row for row in ER._eligible(world) if row['primary'] and row['source_scene'] == 1)
        mapping = identity(world)
        exchange_pairs(mapping, source['id'], target['id'])
        with self.assertRaisesRegex(OptionError, 'own dungeon'):
            ER.validate_mapping(world, mapping)
        ER.validate_mapping(world, mapping, legacy_dungeon_pools=True)
        REPORT_FACTS['legacy_cross_dungeon_pair'] = [source['id'], target['id']]

    def test_old_forward_only_outside_destination_is_only_accepted_as_legacy(self):
        world = world_for(shuffle_dungeon_doors=1, shuffle_one_way_entrances=1)
        source = ER.ENDPOINTS[8610]
        legacy_target = ER._one_way_targets(world, source, legacy_dungeon_pools=True)[0]
        mapping = identity(world)
        mapping[source['id']] = legacy_target['id']
        with self.assertRaisesRegex(OptionError, 'own dungeon'):
            ER.validate_mapping(world, mapping)
        ER.validate_mapping(world, mapping, legacy_dungeon_pools=True)

    def test_explicit_room_and_interior_mix_allows_outside_destinations(self):
        world = world_for(shuffle_dungeon_doors=1, shuffle_interior_entrances=1,
                          mixed_entrance_pools={'dungeon_doors', 'interiors'})
        mapping = identity(world)
        exchange_pairs(mapping, 8192, 626)
        ER.validate_mapping(world, mapping)
        self.assertEqual(ER.ENDPOINTS[mapping[8192]]['category'], 'interiors')
        self.assertEqual(ER.native_settings(world)['DungeonDoorMixedOutside'], 1)

    def test_explicit_mixed_forward_only_shutter_can_leave_dungeon(self):
        world = world_for(shuffle_dungeon_doors=1, shuffle_one_way_entrances=1,
                          shuffle_interior_entrances=1,
                          mixed_entrance_pools={'dungeon_doors', 'interiors'})
        source = ER.ENDPOINTS[8610]
        targets = ER._one_way_targets(world, source)
        self.assertIn('interiors', {row['category'] for row in targets})
        mapping = identity(world)
        mapping[source['id']] = next(row['id'] for row in targets if row['category'] == 'interiors')
        ER.validate_mapping(world, mapping)

    def test_dungeon_only_mix_keeps_dungeon_spawn_return_mode(self):
        for category in ('dungeons', 'bosses'):
            world = world_for(shuffle_dungeon_doors=1, **{ER.CATEGORIES[category]: 1},
                              mixed_entrance_pools={'dungeon_doors', category})
            self.assertTrue(ER.dungeon_doors_are_mixed(world))
            self.assertFalse(ER.dungeon_doors_mix_outside(world))
            self.assertEqual(ER.native_settings(world)['DungeonDoorMixedOutside'], 0)
            mapping = ER._candidate(world)
            ER.validate_mapping(world, mapping)
            self.assertTrue(any(ER.ENDPOINTS[source]['category'] != ER.ENDPOINTS[target]['category']
                                for source, target in mapping.items()))

    def test_boss_shuffle_remains_a_separate_global_boss_pool(self):
        world = world_for(shuffle_dungeon_doors=1, shuffle_boss_entrances=1)
        mapping = ER._candidate(world)
        self.assert_local(world, mapping)
        bosses = [row for row in ER._eligible(world) if row['category'] == 'bosses']
        self.assertTrue(any(mapping[row['id']] != row['id'] for row in bosses))
        self.assertTrue(all(ER.ENDPOINTS[mapping[row['id']]]['category'] == 'bosses' for row in bosses))

    def test_local_ruto_carrier_doors_are_never_moved_by_new_pool_partition(self):
        for selected in (set(), {'all'}):
            world = world_for(shuffle_dungeon_doors=1, shuffle_interior_entrances=1,
                              mixed_entrance_pools=selected)
            mapping = ER._candidate(world)
            self.assertTrue(ER.LOCAL_CARRIER_DOORS)
            self.assertTrue(all(mapping[door] == door for door in ER.LOCAL_CARRIER_DOORS))

    def test_all_uses_enabled_categories_and_matches_explicit_enabled_selection(self):
        options = dict(shuffle_dungeon_doors=1, shuffle_dungeon_entrances=1,
                       shuffle_boss_entrances=1, shuffle_one_way_entrances=1)
        all_world = world_for(**options, mixed_entrance_pools={'all'})
        selected = set(ER.enabled_categories(all_world))
        explicit_world = world_for(**options, mixed_entrance_pools=selected)
        self.assertEqual(ER.mixed_categories(all_world), selected)
        self.assertEqual(ER._candidate(all_world), ER._candidate(explicit_world))
        self.assertEqual(ER.native_settings(all_world), ER.native_settings(explicit_world))
        self.assertEqual(all_world.options.mixed_entrance_pools.value, {'all'})

    def test_return_mode_and_mask_cover_every_category_enabled_and_disabled(self):
        for category, option in ER.CATEGORIES.items():
            if category == 'dungeon_doors':
                continue
            for enabled in (0, 1):
                for selected in ({'dungeon_doors', category}, {'all'}):
                    with self.subTest(category=category, enabled=enabled, selected=selected):
                        world = world_for(shuffle_dungeon_doors=1, **{option: enabled},
                                          mixed_entrance_pools=selected)
                        native = ER.native_settings(world)
                        expected = int(bool(enabled) and category not in ER.DUNGEON_CATEGORIES)
                        self.assertEqual(native['DungeonDoorMixedOutside'], expected)
                        mask = ER.MIXED_CATEGORY_BITS['dungeon_doors'] | (
                            ER.MIXED_CATEGORY_BITS[category] if enabled else 0)
                        self.assertEqual(native['EntranceMixedPoolMask'], mask)
                        self.assertEqual(native['EntrancePoolPolicyRevision'], ER.POOL_POLICY_REVISION)
                        slot = ER.slot_data(world)
                        self.assertEqual(slot['dungeon_door_mixed_outside'], expected)
                        self.assertEqual(slot['effective_mixed_categories'], sorted(ER.mixed_categories(world)))

    def test_disabled_door_option_never_requests_previous_scene(self):
        world = world_for(shuffle_overworld_entrances=1, shuffle_interior_entrances=1,
                          mixed_entrance_pools={'all', 'dungeon_doors'})
        self.assertFalse(ER.dungeon_doors_are_mixed(world))
        self.assertEqual(ER.native_settings(world)['DungeonDoorMixedOutside'], 0)
        world = world_for(mixed_entrance_pools={'all'})
        native = ER.native_settings(world)
        for key in ('DungeonDoorMixedOutside', 'EntranceMixedPoolMask', 'EntrancePoolPolicyRevision'):
            self.assertEqual(native[key], 0)
            self.assertEqual(NATIVE_AP_DEFAULTS[key], 0)

    def test_saved_pool_policy_revision_is_not_silently_upgraded(self):
        world = world_for(shuffle_dungeon_doors=1)
        self.assertEqual(ER.slot_data(world)['pool_policy_revision'], 1)
        world.using_ut = True
        for saved, expected in (({}, 0), ({'pool_policy_revision': 1}, 1)):
            world.passthrough = {'entrance_randomizer': saved}
            self.assertEqual(ER.slot_data(world)['pool_policy_revision'], expected)
            self.assertEqual(ER.native_settings(world)['EntrancePoolPolicyRevision'], expected)

    def test_production_connect_accepts_only_within_dungeon_door_routes(self):
        mw = setup_multiworld(SohExtremeWorld, seed=18902, options={
            'shuffle_dungeon_doors': 1, 'shuffle_one_way_entrances': 1,
            'starting_age': 'child', 'closed_forest': 'off',
        }, steps=('generate_early', 'create_regions', 'create_items', 'set_rules'))
        world = mw.worlds[1]
        ER.connect(world)
        mapping = {source: target for source, target in world._er_mapping.items()
                   if source in {row['id'] for row in ER._eligible(world)}}
        self.assert_local(world, mapping)
        self.assertGreater(world._er_generation_attempts, 0)
        self.assertTrue(any(source != target for source, target in mapping.items()
                            if ER.ENDPOINTS[source]['category'] == 'dungeon_doors'))
        REPORT_FACTS['production_connect'] = dict(
            mapped_sources=len(mapping), accepted_placements=world._er_generation_attempts,
            changed_room_doors=sum(source != target for source, target in mapping.items()
                                  if ER.ENDPOINTS[source]['category'] == 'dungeon_doors'),
            same_dungeon_room_doors=sum(ER.ENDPOINTS[source]['category'] == 'dungeon_doors'
                                       for source in mapping),
            mapping=mapping)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    source_files = ('archipelago/soh_extreme/EntranceRandomizer.py',
                    'archipelago/soh_extreme/EntranceOptions.py',
                    'archipelago/soh_extreme/NativeSettings.py',
                    'archipelago/soh_extreme/EntranceCatalog.json',
                    'archipelago/soh_extreme/EntranceSafety.py',
                    'archipelago/soh_extreme/EntranceDestinationPolicy.json')
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files}
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DungeonDoorPoolTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert hashes == {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files}
    report = dict(status='passed' if result.wasSuccessful() else 'failed', tests_run=result.testsRun,
                  failures=[str(test) for test, _ in result.failures], errors=[str(test) for test, _ in result.errors],
                  runtime_version=Utils.__version__, loaded_world_source=inspect.getfile(SohExtremeWorld),
                  source_sha256=hashes, probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  elapsed_seconds=round(time.monotonic() - started, 3), facts=REPORT_FACTS,
                  scope='Actual AP option types and reviewed endpoint catalog; candidate pools, '
                        'forward-only destinations, coupled mapping validation, legacy-map policy '
                        'and effective return metadata. Includes one production connect() pass; '
                        'no item fill or native gameplay.')
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
